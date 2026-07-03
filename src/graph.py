"""LangGraph 编排:截图 -> 梗图。

节点顺序:S0 -> S1 -> S2 -(拦截?)-> S3 -> S4 -> S5 -(通过/重写/放弃)-> S6 -> END

条件分支:
  - S2 越界 -> 直接 END(blocked)
  - S5 不合规且未超重试 -> 回 S4 重写;超上限 -> END

人机回环(可选):在 S1 之后 interrupt,让用户纠正 Context JSON 里的角色,
resume 后从 S4 继续,不必重跑昂贵的视觉调用。
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.state import MemeState, MAX_REWRITE
from src.nodes import (
    preprocess,
    understand,
    input_safety,
    pick_style,
    generate,
    output_safety,
    compose,
)


def route_after_s2(state: MemeState) -> str:
    return "blocked" if state.get("blocked") else "ok"


def route_after_s5(state: MemeState) -> str:
    safety = state.get("safety") or {}
    if safety.get("output_ok"):
        return "pass"
    if state.get("retry_count", 0) < MAX_REWRITE:
        return "rewrite"
    return "give_up"


def build_graph(*, interrupt_for_role_fix: bool = False):
    g = StateGraph(MemeState)

    g.add_node("preprocess", preprocess)        # S0
    g.add_node("understand", understand)        # S1
    g.add_node("input_safety", input_safety)    # S2
    g.add_node("pick_style", pick_style)        # S3
    g.add_node("generate", generate)            # S4
    g.add_node("output_safety", output_safety)  # S5
    g.add_node("compose", compose)              # S6

    g.set_entry_point("preprocess")
    g.add_edge("preprocess", "understand")
    g.add_edge("understand", "input_safety")

    # S2 拦截分支
    g.add_conditional_edges(
        "input_safety", route_after_s2,
        {"blocked": END, "ok": "pick_style"},
    )

    g.add_edge("pick_style", "generate")
    g.add_edge("generate", "output_safety")

    # S5:通过 -> S6 / 重写 -> 回 S4 / 放弃 -> END
    g.add_conditional_edges(
        "output_safety", route_after_s5,
        {"pass": "compose", "rewrite": "generate", "give_up": END},
    )

    g.add_edge("compose", END)

    checkpointer = MemorySaver()  # 支持断点续跑 / interrupt 回放
    # 需要"用户纠正角色"时,在 S1 之后中断,前端改完 context 再 resume
    interrupt_after = ["understand"] if interrupt_for_role_fix else []
    return g.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)


# 默认导出一个编译好的 app
app = build_graph()
