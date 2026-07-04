"""本地跑通整条图→图流程的入口。

    python main.py <截图路径> [gif]

末尾追加 gif 参数时使用 templates/gif/ 下的动图底图，否则使用 templates/img/。
"""

import sys
import time
import base64

from src.graph import app

# 日志中超过此长度的字符串值直接截断
_MAX_STR_LEN = 60


def load_image_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def _fmt_value(v) -> str:
    """格式化单个值，长字符串截断显示。"""
    if isinstance(v, str) and len(v) > _MAX_STR_LEN:
        return f"<str len={len(v)}>"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_fmt_value(val)}" for k, val in v.items()) + "}"
    if isinstance(v, list):
        return f"[{len(v)} items]" if len(v) > 3 else str(v)
    return repr(v)


def _fmt_partial(partial: dict) -> str:
    return "{" + ", ".join(f"{k}: {_fmt_value(v)}" for k, v in partial.items()) + "}"


def main() -> None:
    args = sys.argv[1:]
    media_type = "gif" if "gif" in args else "img"
    image_path = next((a for a in args if a != "gif"), "")
    image_b64 = load_image_b64(image_path) if image_path else ""

    initial: dict = {"image_b64": image_b64, "media_type": media_type}
    config = {"configurable": {"thread_id": "demo-1"}}

    total_start = time.time()
    print(f"\n{'='*40}")
    print(f"  模式: {media_type}  |  输入: {image_path or '(无)'}")
    print(f"{'='*40}")

    node_start = total_start
    for step in app.stream(initial, config=config):
        for node_name, partial in step.items():
            elapsed = (time.time() - node_start) * 1000
            print(f"  [{node_name:<18}] {elapsed:>6.0f}ms  {_fmt_partial(partial)}")
            node_start = time.time()

    total_elapsed = time.time() - total_start
    final = app.get_state(config).values

    print(f"{'='*40}")
    status = final.get("status", "-")
    blocked = final.get("blocked", False)
    final_image = final.get("final_image", None)
    print(f"  状态:    {status}")
    print(f"  拦截:    {blocked}")
    print(f"  输出:    {final_image or '(无)'}")
    print(f"  总耗时:  {total_elapsed:.2f}s")
    print(f"{'='*40}\n")


if __name__ == "__main__":
    main()
