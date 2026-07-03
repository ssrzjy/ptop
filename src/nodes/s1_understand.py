"""S1 视觉理解 —— 整条流程最关键的一步。

用 Claude Opus 4.8(高分辨率视觉)看懂截图:对话双方、角色、语气、
潜台词、情绪、PUA 类型。用 structured output 强制输出 Context JSON。

打磨方向:把下面的桩替换为真实的 client.messages.create 调用,
schema 用 CONTEXT_SCHEMA 约束。可以顺带在同一次调用里输出 safety 字段,
省掉 S2 的一次模型调用。
"""

import json
import base64

from src.state import MemeState
from src.config import get_model
from src.llm import get_client

# Context JSON 的结构契约(structured output 的 schema 基础)
CONTEXT_SCHEMA = {
    "type": "object",
    "properties": {
        "participants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "role": {"type": "string"},  # "对方" / "我"
                },
                "required": ["id", "role"],
                "additionalProperties": False,
            },
        },
        "dialogue": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "text": {"type": "string"},
                    "tone": {"type": "string"},
                },
                "required": ["speaker", "text", "tone"],
                "additionalProperties": False,
            },
        },
        "subtext": {"type": "string"},
        "emotion": {"type": "string"},
        "pua_type": {"type": "string"},
    },
    "required": ["participants", "dialogue", "subtext", "emotion", "pua_type"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = (
    "你是分析聊天截图的助手。看懂截图里的对话:谁在说话、说了什么、语气、"
    "潜台词、情绪,以及对方是否在 PUA(职场PUA/情感PUA/道德绑架 等)。"
    "只输出符合给定 JSON schema 的结果,不要多余文字。"
)


def _detect_mime(image_b64: str) -> str:
    """从 base64 首字节探测图片类型,不依赖文件后缀。"""
    head = base64.b64decode(image_b64[:16])
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/png"  # 兜底


def understand(state: MemeState) -> dict:
    cfg = get_model("s1_understand")  # 本阶段用哪个模型,由 config.py 决定
    client = get_client(cfg)

    image_b64 = state.get("image_b64", "")
    content = [
        {"type": "text", "text": "分析这张聊天截图,按 schema 输出 Context JSON。"},
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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "context", "schema": CONTEXT_SCHEMA},
        },
    )
    context = json.loads(resp.choices[0].message.content)
    return {"context": context}
