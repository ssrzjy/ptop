"""S6 合成 —— 出图。

img 模式：Pillow 读静态图贴字，输出 PNG。
gif 模式：cv2 逐帧读 mp4，文字层只渲染一次后 numpy 广播叠加，输出动态 GIF。
"""

import os
import glob

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
TEXT_MARGIN_RATIO = 0.045
TEXT_BAND_RATIO = 0.22
TEXT_MIN_FONT_SIZE = 12


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _find_template_path(template_id: str, media_type: str) -> str | None:
    d = os.path.join(TEMPLATES_BASE, media_type)
    matches = glob.glob(os.path.join(d, f"{template_id}.*"))
    return matches[0] if matches else None


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
    stroke_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in (text or "").replace("\r\n", "\n").split("\n"):
        current = ""
        for char in paragraph:
            candidate = current + char
            bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=stroke_width)
            if not current or bbox[2] - bbox[0] <= max_width:
                current = candidate
                continue
            lines.append(current.strip())
            current = char
        if current:
            lines.append(current.strip())
    return lines or [""]


def _measure_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.ImageFont,
    line_gap: int,
    stroke_width: int,
) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    bboxes = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width) for line in lines]
    widths = [bbox[2] - bbox[0] for bbox in bboxes]
    heights = [bbox[3] - bbox[1] for bbox in bboxes]
    total_height = sum(heights) + line_gap * max(0, len(lines) - 1)
    return (max(widths) if widths else 0), total_height, bboxes


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box_w: int,
    box_h: int,
    max_font_size: int,
) -> tuple[ImageFont.ImageFont, list[str], list[tuple[int, int, int, int]], int, int]:
    min_size = min(max_font_size, TEXT_MIN_FONT_SIZE)
    best: tuple[ImageFont.ImageFont, list[str], list[tuple[int, int, int, int]], int, int] | None = None

    for size in range(max_font_size, min_size - 1, -1):
        font = _load_font(size)
        stroke_width = max(1, round(size * 0.08))
        line_gap = max(2, round(size * 0.12))
        lines = _wrap_text_to_width(draw, text, font, box_w, stroke_width)
        block_w, block_h, bboxes = _measure_lines(draw, lines, font, line_gap, stroke_width)
        best = (font, lines, bboxes, line_gap, stroke_width)
        if block_w <= box_w and block_h <= box_h:
            return best

    return best or (_load_font(TEXT_MIN_FONT_SIZE), [text or ""], [], 2, 1)


def _caption_box(slot: str, w: int, h: int) -> tuple[int, int, int, int]:
    margin_x = max(8, round(w * TEXT_MARGIN_RATIO))
    margin_y = max(6, round(h * 0.018))
    band_h = max(36, round(h * TEXT_BAND_RATIO))
    band_h = min(band_h, max(36, h // 3))
    box_w = max(1, w - margin_x * 2)

    if slot == "bottom":
        return margin_x, max(0, h - margin_y - band_h), box_w, band_h
    return margin_x, margin_y, box_w, band_h


def _draw_caption(draw: ImageDraw.ImageDraw, text: str, slot: str, w: int, h: int) -> None:
    box_x, box_y, box_w, box_h = _caption_box(slot, w, h)
    max_font_size = max(TEXT_MIN_FONT_SIZE, min(round(h * 0.12), round(w * 0.18), 96))
    font, lines, bboxes, line_gap, stroke_width = _fit_text(
        draw, text, box_w, box_h, max_font_size
    )
    _, block_h, bboxes = _measure_lines(draw, lines, font, line_gap, stroke_width)
    while len(lines) > 1 and block_h > box_h:
        lines = lines[:-1]
        lines[-1] = lines[-1].rstrip("...…") + "..."
        _, block_h, bboxes = _measure_lines(draw, lines, font, line_gap, stroke_width)

    y = box_y + max(0, (box_h - block_h) // 2)
    for line, bbox in zip(lines, bboxes):
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        x = box_x + max(0, (box_w - line_w) // 2) - bbox[0]
        draw.text(
            (x, y - bbox[1]),
            line,
            font=font,
            fill="white",
            stroke_width=stroke_width,
            stroke_fill="black",
        )
        y += line_h + line_gap


def _make_text_overlay(w: int, h: int, captions: list) -> np.ndarray:
    """渲染纯透明背景的文字层，返回 RGBA numpy 数组 (H, W, 4)。只调用一次。"""
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for cap in captions:
        text = cap.get("text", "")
        _draw_caption(draw, text, cap.get("slot", "top"), w, h)
    return np.array(overlay)  # (H, W, 4)


def _blend_overlay(frame_rgb: np.ndarray, overlay_rgba: np.ndarray) -> np.ndarray:
    """将 RGBA 文字层 alpha 合成到 RGB 帧上，返回 RGB numpy 数组。"""
    alpha = overlay_rgba[:, :, 3:4].astype(np.float32) / 255.0
    text_rgb = overlay_rgba[:, :, :3].astype(np.float32)
    frame_f = frame_rgb.astype(np.float32)
    blended = frame_f * (1 - alpha) + text_rgb * alpha
    return blended.astype(np.uint8)


def _apply_captions(img: Image.Image, captions: list) -> Image.Image:
    """静态图模式：直接在图上绘制文字。"""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for cap in captions:
        text = cap.get("text", "")
        _draw_caption(draw, text, cap.get("slot", "top"), w, h)
    return img


def _compose_img(path: str | None, template_id: str, captions: list) -> str:
    if path:
        img = Image.open(path).convert("RGB")
    else:
        img = Image.new("RGB", (800, 800), (40, 44, 52))

    img = _apply_captions(img, captions)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{template_id}.png")
    img.save(out_path)
    return os.path.abspath(out_path)


def _compose_gif(path: str | None, template_id: str, captions: list) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{template_id}.gif")

    if not path:
        img = Image.new("RGB", (480, 360), (40, 44, 52))
        img = _apply_captions(img, captions)
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
    overlay = _make_text_overlay(out_w, out_h, captions)

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
