"""S1 视觉理解 + 文案生成 —— 合并为单次模型调用。

一次调用完成：
  1. 看懂截图，识别 pua_type
  2. 直接生成贴到梗图上的 captions（top/bottom，≤15字）
  3. 判断是否越界（blocked），省掉单独的安全节点调用
"""

import json
import base64

from src.state import MemeState
from src.config import get_model
from src.llm import get_client
from src.meme_fetcher import meme_list_for_prompt

COMBINED_SCHEMA = {
    "type": "object",
    "properties": {
        "pua_type": {"type": "string"},    # "职场PUA" / "情感PUA" / "道德绑架" / "无"
        "blocked": {"type": "boolean"},    # 违法/极端内容时为 true
        "template_id": {"type": "string"}, # 从梗图列表中选一个 id
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string"},  # "top" / "bottom"
                    "text": {"type": "string"},  # ≤15字
                },
                "required": ["slot", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["pua_type", "blocked", "template_id", "captions"],
    "additionalProperties": False,
}


def _build_system_prompt() -> str:
    meme_list = meme_list_for_prompt()
    return (
        "你是分析聊天截图并生成反PUA梗图文案的助手。\n"
        "1. 看懂截图，识别是否存在PUA/职场压迫/道德绑架等行为，填写 pua_type。\n"
        "2. 若内容涉及违法/未成年人/极端暴力，设 blocked=true，template_id 和 captions 留空。\n"
        "3. 否则：\n"
        "   a. 从下方梗图列表中选一个最贴合当前情绪和回怼语义的模板，填写 template_id。\n"
        "   b. 针对截图里的具体内容，生成两条有杀伤力的配文（每条≤15字）：\n"
        "      - 配文必须紧扣截图中的实际言行，不要泛泛而谈\n"
        "      - 目标是让看到的人觉得又准又狠又好笑\n"
        "      - slot=top 和 slot=bottom 形成对比或反转，具体形式不限\n\n"
        "梗图列表（格式：id|名称）：\n"
        f"{meme_list}\n\n"
        "只输出符合给定 JSON schema 的结果，不要多余文字。"
    )


def _detect_mime(image_b64: str) -> str:
    head = base64.b64decode(image_b64[:16])
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/png"


def understand(state: MemeState) -> dict:
    cfg = get_model("s1_understand")
    client = get_client(cfg)

    image_b64 = state.get("image_b64", "")
    content = [
        {"type": "text", "text": "分析这张聊天截图，按 schema 输出结果。"},
    ]
    if image_b64:
        mime = _detect_mime(image_b64)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
        })

    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "context", "schema": COMBINED_SCHEMA},
        },
    )
    context = json.loads(resp.choices[0].message.content)
    return {"context": context, "blocked": context.get("blocked", False)}
