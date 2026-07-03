"""S3 选风格 —— 纯规则,不调模型,省成本和延迟。

按 Context JSON 里的 pua_type 映射到回怼风格。后续可扩成更细的规则表
或用户可选。
"""

from src.state import MemeState

# pua_type -> 回怼风格
STYLE_MAP = {
    "职场PUA": "犀利吐槽",
    "情感PUA": "温和反击",
    "道德绑架": "阴阳怪气",
}
DEFAULT_STYLE = "犀利吐槽"


def pick_style(state: MemeState) -> dict:
    context = state.get("context") or {}
    pua_type = context.get("pua_type", "")
    style = STYLE_MAP.get(pua_type, DEFAULT_STYLE)
    return {"style": style}
