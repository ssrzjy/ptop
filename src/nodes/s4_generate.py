"""S4 文案生成。

用 Claude(Opus 4.8 质量高 / Sonnet 5 走量)按 context + style 生成:
回怼文案、梗图模板选择、贴到图上的文字。structured output 输出 Generation JSON。

被 S5 打回重写时也会再进入本节点,retry_count 已在 S5 累加。
"""

import json
import os

from src.state import MemeState
from src.config import get_model
from src.llm import get_client

TEMPLATES_BASE = "templates"


def _available_templates(media_type: str = "img") -> list[str]:
    """读 templates/<media_type>/ 目录，返回不含扩展名的 id 列表。"""
    d = os.path.join(TEMPLATES_BASE, media_type)
    if not os.path.isdir(d):
        return []
    return [
        os.path.splitext(f)[0]
        for f in sorted(os.listdir(d))
        if not f.startswith(".")
    ]

GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "reply_text": {"type": "string"},
        "template_id": {"type": "string"},
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string"},   # "top" / "bottom" / ...
                    "text": {"type": "string"},
                },
                "required": ["slot", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["reply_text", "template_id", "captions"],
    "additionalProperties": False,
}


SYSTEM_PROMPT = (
    "你帮用户理性、机智地反击 PUA,不做人身攻击、不辱骂、不违法。"
    "根据对话理解和指定风格,生成一句回怼文案、选一个梗图模板 id、"
    "以及贴到图上的文字(captions,slot 用 top/bottom)。"
    "只输出符合给定 JSON schema 的结果。"
)


def generate(state: MemeState) -> dict:
    context = state.get("context") or {}
    style = state.get("style", "")
    cfg = get_model("s4_generate")  # 本阶段用哪个模型,可与 S1 不同
    client = get_client(cfg)

    media_type = state.get("media_type", "img")
    templates = _available_templates(media_type)
    template_hint = (
        f"可用模板 id(必须从中选一个):{templates}\n" if templates else ""
    )
    user_prompt = (
        f"对话理解(Context JSON):{json.dumps(context, ensure_ascii=False)}\n"
        f"回怼风格:{style}\n"
        f"{template_hint}"
        "请生成 Generation JSON。"
    )
    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "generation", "schema": GENERATION_SCHEMA},
        },
    )
    generation = json.loads(resp.choices[0].message.content)
    return {"generation": generation}
