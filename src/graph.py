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

from src.state import MemeState
from src.nodes import (
    preprocess,
    understand,
    input_safety,
    compose,
)


def route_after_s2(state: MemeState) -> str:
    return "blocked" if state.get("blocked") else "ok"


def build_graph(*, interrupt_for_role_fix: bool = False):
    g = StateGraph(MemeState)

    g.add_node("preprocess", preprocess)     # S0
    g.add_node("understand", understand)     # S1：识图 + 生成 captions
    g.add_node("input_safety", input_safety) # S2：透传 S1 的 blocked 字段
    g.add_node("compose", compose)           # S6：随机选底图 + 贴字

    g.set_entry_point("preprocess")
    g.add_edge("preprocess", "understand")
    g.add_edge("understand", "input_safety")

    g.add_conditional_edges(
        "input_safety", route_after_s2,
        {"blocked": END, "ok": "compose"},
    )

    g.add_edge("compose", END)

    checkpointer = MemorySaver()
    interrupt_after = ["understand"] if interrupt_for_role_fix else []
    return g.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)


# 默认导出一个编译好的 app
app = build_graph()
