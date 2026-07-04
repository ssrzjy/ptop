"""增强模式出图(S6-enhanced)。

与极速模式(compose:按模板贴字)并列的另一条出图路线。
用大模型(gpt-image-1)把 原始截图 + 识图结果 + S4 回怼话
一起喂进去,直接生成一张全新的、更贴合语境的回怼梗图(图里已含中文)。

前面 S0~S5 与极速模式完全共用,只在此处分叉。
"""

import os
import io
import base64
from datetime import datetime

from PIL import Image

from src.state import MemeState
from src.config import get_model
from src.llm import generate_image_b64

OUTPUT_DIR = "output"


def _build_prompt(context: dict, reply_text: str, style: str) -> str:
    dialogue = context.get("dialogue", [])
    said = "；".join(d.get("text", "") for d in dialogue if d.get("text"))
    pua = context.get("pua_type", "")
    emotion = context.get("emotion", "")
    return (
        "这是一张聊天截图,对方在 PUA/打压对话对象。"
        "请生成一张中文互联网风格、极具攻击力和嘲讽感的斗图表情包(meme),"
        "用来狠狠地、一击致命地怼回去。\n"
        f"对方大意:{said or '(打压 / 说教 / 制造焦虑)'}\n"
        f"套路类型:{pua};氛围:{emotion};回怼风格:{style}\n"
        f"图上要用超大、醒目、有冲击力的中文字写这句回怼话:「{reply_text}」\n"
        "画面要求:\n"
        "- 主体是一个表情夸张、气场极强的卡通角色(如翻白眼、冷笑、鄙视、"
        "居高临下俯视、抱臂嘲讽等挑衅姿态),要有一眼就'压过对方'的气势;\n"
        "- 文字排版张扬:大号粗体、描边或高对比配色(如红黑/黄黑),"
        "关键词可以更大更突出,像热门怼人表情包那样有'糊脸'的冲击力;\n"
        "- 背景简洁不抢戏,可加放射线、感叹号、火焰等强调元素烘托气势;\n"
        "- 中文文字必须清晰、无错字、无多余文字。"
    )


def compose_enhanced(state: MemeState) -> dict:
    context = state.get("context") or {}
    generation = state.get("generation") or {}
    reply_text = generation.get("reply_text", "")
    style = state.get("style", "")

    cfg = get_model("s6_image")
    if not cfg.model:
        raise RuntimeError(
            "增强模式未配置生图模型:请在 .env 设置 "
            "S6_IMAGE_MODEL / S6_BASE_URL(gpt-image-1)"
        )

    prompt = _build_prompt(context, reply_text, style)
    # 图生图:把原始截图一起喂给模型作参考
    b64 = generate_image_b64(cfg, prompt, image_b64=state.get("image_b64") or None)
    img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    path = os.path.join(OUTPUT_DIR, f"enhanced_{ts}.png")
    img.save(path)

    return {"final_image": os.path.abspath(path), "status": "done"}
