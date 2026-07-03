"""标注单张梗图的 slot，用于快速验证效果。

用法：
    python scripts/annotate_one.py <template_id>

示例：
    python scripts/annotate_one.py 50421420
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.annotate_slots import annotate, find_local_path
from src.config import get_model
from src.llm import get_client

META_PATH = "meta.json"


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/annotate_one.py <template_id>")
        sys.exit(1)

    template_id = sys.argv[1]

    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    memes = meta["data"]["memes"]
    meme = next((m for m in memes if m["id"] == template_id), None)
    if not meme:
        print(f"未找到 template_id={template_id}")
        sys.exit(1)

    local_path = find_local_path(template_id)
    if not local_path:
        print(f"本地未找到图片：templates/{template_id}.*")
        sys.exit(1)

    cfg = get_model("s1_understand")
    client = get_client(cfg)

    box_count = meme.get("box_count", 0)
    print(f"标注中：{template_id} {meme['name']} (box_count={box_count}) ...")
    slots = annotate(client, cfg, template_id, local_path, box_count)
    meme["slots"] = slots

    label = f"{len(slots)} 个区域" if slots else "无留白"
    print(f"结果：{label}")
    for s in slots:
        print(f"  {s['slot']}: x={s['x_pct']:.2f} y={s['y_pct']:.2f} "
              f"w={s['w_pct']:.2f} h={s['h_pct']:.2f}")

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"已写回 {META_PATH}")


if __name__ == "__main__":
    main()
