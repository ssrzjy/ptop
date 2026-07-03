"""S6 合成 —— 出图。

MVP 实现:不依赖外部模板素材,直接用 Pillow 画一张纯色背景图,
把 captions 里的文字按 slot(top/bottom)贴上去,导出 PNG 到 output/。

后续增强:接入 templates/{template_id}.png 素材库,按 slot 坐标贴字;
或改成文生图模型出背景。
"""

import os
import textwrap

from PIL import Image, ImageDraw, ImageFont

from src.state import MemeState

OUTPUT_DIR = "output"
# macOS 自带中文字体;换机器时改这里
FONT_PATH = os.environ.get("MEME_FONT", "/System/Library/Fonts/STHeiti Medium.ttc")
W, H = 800, 800


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except OSError:
        return ImageFont.load_default()


def _draw_text(draw: ImageDraw.ImageDraw, text: str, y: int, font) -> None:
    # 按宽度折行,居中,带黑描边(梗图风格)
    for i, line in enumerate(textwrap.wrap(text, width=12) or [""]):
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (W - (bbox[2] - bbox[0])) // 2
        draw.text((x, y + i * (font.size + 8)), line, font=font,
                  fill="white", stroke_width=3, stroke_fill="black")


def compose(state: MemeState) -> dict:
    generation = state.get("generation") or {}
    template_id = generation.get("template_id", "meme")
    captions = generation.get("captions", [])

    img = Image.new("RGB", (W, H), (40, 44, 52))
    draw = ImageDraw.Draw(img)
    font = _load_font(48)

    for cap in captions:
        text = cap.get("text", "")
        if cap.get("slot") == "bottom":
            _draw_text(draw, text, H - 220, font)
        else:  # top / 其他
            _draw_text(draw, text, 40, font)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # thread_id 拿不到时用 template_id 命名
    path = os.path.join(OUTPUT_DIR, f"{template_id}.png")
    img.save(path)

    return {"final_image": os.path.abspath(path), "status": "done"}
