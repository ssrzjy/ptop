"""S2 输入安全。

基于 S1 的 Context JSON 判断:是否真的是 PUA/负面内容,是否越界
(违法、涉及未成年人等)。越界则置 blocked=True,图会路由到 END。

打磨方向:可与 S1 合并为一次调用;或接入独立的内容审核规则/模型。
"""

from src.state import MemeState


def input_safety(state: MemeState) -> dict:
    context = state.get("context") or {}
    # TODO: 真实的越界判定(违法/未成年/极端等)
    blocked = False
    reason = None
    return {
        "safety": {"is_negative": True, "blocked": blocked, "reason": reason},
        "blocked": blocked,
        "status": "blocked" if blocked else "running",
    }
