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
                    # 只允许 top/bottom，和 compose 的放置逻辑一一对应，
                    # 避免出现未知 slot 时全部 fallback 到顶部造成重叠。
                    "slot": {"type": "string", "enum": ["top", "bottom"]},
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
    "你帮用户狠狠地、解气地反击 PUA。火力全开,言辞可以激烈、可以带情绪、"
    "可以用接地气的脏话和网络烂梗,目标是一句话噎死对方、让读者拍手叫好。\n"
    "\n"
    "【火力要求】\n"
    "- 别端着、别讲道理、别客气,要像真人吵架那样又冲又痞。\n"
    "- 允许脏字和粗口(如\"滚\"\"闭嘴\"\"关你屁事\"这类),但要用在刀刃上,"
    "为了狠而狠、通篇脏话反而没杀伤力。\n"
    "- 火力全部对准【对方的话术、逻辑和双标】:把他的话原样怼回去、"
    "戳破他的双标、拆穿他的PUA包装——这才是真的狠。\n"
    "- 不做基于性别、地域、长相、身份、种族等的无差别人身歧视,"
    "那不是怼,是掉价,读者只会觉得你输了。\n"
    "\n"
    "根据对话理解和指定风格,生成一句回怼文案、选一个梗图模板 id、"
    "以及贴到图上的文字(captions)。\n"
    "\n"
    "【captions 排版规则,必须严格遵守,否则文字会溢出或互相遮挡】\n"
    "1. captions 最多 2 条:一条 slot=\"top\"(贴顶部),一条 slot=\"bottom\"(贴底部)。"
    "宁可只用 1 条,也不要为了凑数硬塞。\n"
    "2. 每条 text 控制在 12 个汉字以内,确保单行显示;绝对不要超过 16 个汉字。"
    "长句要精简成短促有力的一句,而不是完整的长句。\n"
    "3. top 和 bottom 各只放 1 条,不要把两句话都塞进同一个 slot。\n"
    "4. 梗图讲究「短、狠、有节奏」:优先用最精炼、最有冲击力的表达,"
    "把最有力的反击点放在 bottom。\n"
    "5. 不要在 text 里加引号、书名号或多余标点;结尾标点最多一个。\n"
    "\n"
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
