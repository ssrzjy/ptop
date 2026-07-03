"""本地跑通整条图→图流程的入口。

    python main.py <截图路径>

现在所有节点是桩,会打印每步产出;打磨时逐个替换 src/nodes/ 下的实现。
"""

import sys
import time
import base64

from src.graph import app


def load_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def main() -> None:
    image_b64 = load_image_b64(sys.argv[1]) if len(sys.argv) > 1 else ""

    initial: dict = {"image_b64": image_b64}
    config = {"configurable": {"thread_id": "demo-1"}}  # checkpointer 需要

    total_start = time.time()
    print("=== 开始 ===")

    node_start = total_start
    for step in app.stream(initial, config=config):
        for node_name, partial in step.items():
            now = time.time()
            elapsed = now - node_start
            print(f"[{node_name}] {elapsed*1000:.0f}ms -> {partial}")
            node_start = now

    total_elapsed = time.time() - total_start
    final = app.get_state(config).values
    print(f"=== 结束 (总耗时 {total_elapsed:.2f}s) ===")
    print("status:", final.get("status"))
    print("blocked:", final.get("blocked"))
    print("final_image:", final.get("final_image"))


if __name__ == "__main__":
    main()
