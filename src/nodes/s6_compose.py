"""S6 合成 —— 出图。

MVP 实现:不依赖外部模板素材,直接用 Pillow 画一张纯色背景图,
把 captions 里的文字按 slot(top/bottom)贴上去,导出 PNG 到 output/。

后续增强:接入 templates/{template_id}.png 素材库,按 slot 坐标贴字;
或改成文生图模型出背景。
"""

import os
import glob
import textwrap

from PIL import Image, ImageDraw, ImageFont

from src.state import MemeState

OUTPUT_DIR = "output"
TEMPLATES_DIR = "templates"
FONT_PATH = os.environ.get(
    "MEME_FONT",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux 默认中文字体
)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _load_template(template_id: str) -> Image.Image:
    """按 template_id 查找模板文件，支持任意扩展名；找不到则用纯色背景。"""
    for path in glob.glob(os.path.join(TEMPLATES_DIR, f"{template_id}.*")):
        return Image.open(path).convert("RGB")
    return Image.new("RGB", (800, 800), (40, 44, 52))


def _draw_text(draw: ImageDraw.ImageDraw, text: str, y: int, w: int, font) -> None:
    # 按宽度折行,居中,带黑描边(梗图风格)
    for i, line in enumerate(textwrap.wrap(text, width=12) or [""]):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw.text((x, y + i * (font.size + 8)), line, font=font,
                  fill="white", stroke_width=3, stroke_fill="black")


def compose(state: MemeState) -> dict:
    context = state.get("context") or {}
    captions = context.get("captions", [])
    template_id = context.get("template_id", "")

    img = _load_template(template_id)
    w, h = img.size
    draw = ImageDraw.Draw(img)
    font_size = max(24, h // 12)
    font = _load_font(font_size)

    for cap in captions:
        text = cap.get("text", "")
        if cap.get("slot") == "bottom":
            _draw_text(draw, text, h - font_size * 3, w, font)
        else:
            _draw_text(draw, text, font_size // 2, w, font)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{template_id}.png")
    img.save(path)

    return {"final_image": os.path.abspath(path), "status": "done"}
