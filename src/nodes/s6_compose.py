"""S6 合成 —— 出图。

img 模式：Pillow 读静态图贴字，输出 PNG。
gif 模式：cv2 逐帧读 mp4，文字层只渲染一次后 numpy 广播叠加，输出动态 GIF。
"""

import os
import glob
import textwrap

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from src.state import MemeState

OUTPUT_DIR = "output"
TEMPLATES_BASE = "templates"
FONT_PATH = os.environ.get(
    "MEME_FONT",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)

GIF_MAX_WIDTH = 480   # 输出 gif 最大宽度，超出等比缩小
GIF_MAX_FPS   = 12    # 输出 gif 最高帧率，超出则跳帧


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _find_template_path(template_id: str, media_type: str) -> str | None:
    d = os.path.join(TEMPLATES_BASE, media_type)
    matches = glob.glob(os.path.join(d, f"{template_id}.*"))
    return matches[0] if matches else None


def _draw_text(draw: ImageDraw.ImageDraw, text: str, y: int, w: int, font) -> None:
    for i, line in enumerate(textwrap.wrap(text, width=12) or [""]):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw.text((x, y + i * (font.size + 8)), line, font=font,
                  fill="white", stroke_width=3, stroke_fill="black")


def _make_text_overlay(w: int, h: int, captions: list, font) -> np.ndarray:
    """渲染纯透明背景的文字层，返回 RGBA numpy 数组 (H, W, 4)。只调用一次。"""
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_size = font.size
    for cap in captions:
        text = cap.get("text", "")
        if cap.get("slot") == "bottom":
            _draw_text(draw, text, h - font_size * 3, w, font)
        else:
            _draw_text(draw, text, font_size // 2, w, font)
    return np.array(overlay)  # (H, W, 4)


def _blend_overlay(frame_rgb: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
    """将 RGBA 文字层 alpha 合成到 RGB 帧上，返回 RGB numpy 数组。"""
    alpha = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
    text_rgb = overlay_rgba[:, :, :3].astype(np.float32)
    frame_f = frame_rgb.astype(np.float32)
    blended = frame_f * (1 - alpha) + text_rgb * alpha
    return blended.astype(np.uint8)


def _apply_captions(img: Image.Image, captions: list, font) -> Image.Image:
    """静态图模式：直接在图上绘制文字。"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    font_size = font.size
    for cap in captions:
        text = cap.get("text", "")
        if cap.get("slot") == "bottom":
            _draw_text(draw, text, h - font_size * 3, w, font)
        else:
            _draw_text(draw, text, font_size // 2, w, font)
    return img


def _compose_img(path: str | None, template_id: str, captions: list) -> str:
    if path:
        img = Image.open(path).convert("RGB")
    else:
        img = Image.new("RGB", (800, 800), (40, 44, 52))

    font = _load_font(max(24, img.height // 12))
    img = _apply_captions(img, captions, font)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{template_id}.png")
    img.save(out_path)
    return os.path.abspath(out_path)


def _compose_gif(path: str | None, template_id: str, captions: list) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{template_id}.gif")

    if not path:
        img = Image.new("RGB", (480, 360), (40, 44, 52))
        font = _load_font(40)
        img = _apply_captions(img, captions, font)
        img.save(out_path)
        return os.path.abspath(out_path)

    cap = cv2.VideoCapture(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or 24
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 等比缩放到 GIF_MAX_WIDTH
    scale = min(1.0, GIF_MAX_WIDTH / src_w)
    out_w = int(src_w * scale)
    out_h = int(src_h * scale)

    # 跳帧：src_fps → GIF_MAX_FPS
    step = max(1, round(src_fps / GIF_MAX_FPS))
    out_fps = src_fps / step
    duration_ms = int(1000 / out_fps)

    # 只渲染一次文字层
    font = _load_font(max(24, out_h // 12))
    overlay = _make_text_overlay(out_w, out_h, captions, font)

    frames: list[Image.Image] = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            if scale < 1.0:
                frame = cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            blended = _blend_overlay(rgb, overlay)
            frames.append(Image.fromarray(blended))
        idx += 1
    cap.release()

    if not frames:
        return _compose_img(None, template_id, captions)

    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        loop=0,
        duration=duration_ms,
        optimize=False,
    )
    return os.path.abspath(out_path)


def compose(state: MemeState) -> dict:
    context = state.get("context") or {}
    captions = context.get("captions", [])
    template_id = context.get("template_id", "")
    media_type = state.get("media_type", "img")

    path = _find_template_path(template_id, media_type)

    if media_type == "gif":
        out = _compose_gif(path, template_id, captions)
    else:
        out = _compose_img(path, template_id, captions)

    return {"final_image": out, "status": "done"}
