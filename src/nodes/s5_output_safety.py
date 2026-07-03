"""S5 输出安全。

审核 S4 生成的 reply_text / captions:避免人身攻击、违法、过激内容。
- 通过        -> compose(S6)
- 不合规且未超重试 -> 回 S4 重写(retry_count += 1)
- 超过重试上限   -> 放弃(END)

路由逻辑见 graph.py 的 route_after_s5。
"""

from src.state import MemeState


def output_safety(state: MemeState) -> dict:
    generation = state.get("generation") or {}
    # TODO: 真实审核(规则 + 模型双保险)
    passed = True  # 桩:默认通过
    if passed:
        return {"safety": {**(state.get("safety") or {}), "output_ok": True}}
    # 不合规:累加重试计数,route_after_s5 会据此决定回 S4 还是放弃
    return {
        "safety": {**(state.get("safety") or {}), "output_ok": False},
        "retry_count": state.get("retry_count", 0) + 1,
    }
