"""S2 输入安全。

基于 S1 的 Context JSON 判断:是否真的是 PUA/负面内容,是否越界
(违法、涉及未成年人等)。越界则置 blocked=True,图会路由到 END。

打磨方向:可与 S1 合并为一次调用;或接入独立的内容审核规则/模型。
"""

from src.state import MemeState


def input_safety(state: MemeState) -> dict:
    # blocked 已由 S1 在单次调用中判断并写入 state，此处直接透传
    blocked = state.get("blocked", False)
    return {
        "safety": {"blocked": blocked},
        "blocked": blocked,
        "status": "blocked" if blocked else "running",
    }
