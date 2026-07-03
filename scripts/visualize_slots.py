"""可视化验证单张梗图的 slot 标注位置。

用法：
    python scripts/visualize_slots.py <template_id>

示例：
    python scripts/visualize_slots.py 50421420
"""

import os
import sys
import json
import glob

from PIL import Image, ImageDraw, ImageFont

META_PATH = "meta.json"
TEMPLATES_DIR = "templates"
OUTPUT_DIR = "output/debug"


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python scripts/visualize_slots.py <template_id>")
        sys.exit(1)

    template_id = sys.argv[1]

    with open(META_PATH, encoding="utf-8") as f:
        memes = json.load(f)["data"]["memes"]

    meme = next((m for m in memes if m["id"] == template_id), None)
    if not meme:
        print(f"未找到 template_id={template_id}")
        sys.exit(1)

    slots = meme.get("slots")
    if slots is None:
        print(f"{template_id} 尚未标注 slots，请先运行 annotate_slots.py")
        sys.exit(1)

    matches = glob.glob(os.path.join(TEMPLATES_DIR, f"{template_id}.*"))
    if not matches:
        print(f"本地未找到图片文件：templates/{template_id}.*")
        sys.exit(1)

    img = Image.open(matches[0]).convert("RGB")
    w, h = img.size
    draw = ImageDraw.Draw(img)

    if not slots:
        print(f"{meme['name']}：无留白区域（slots=[]）")
    else:
        for slot in slots:
            x = int(slot["x_pct"] * w)
            y = int(slot["y_pct"] * h)
            bw = int(slot["w_pct"] * w)
            bh = int(slot["h_pct"] * h)
            # 画红色边框
            draw.rectangle([x, y, x + bw, y + bh], outline="red", width=3)
            # 左上角标注 slot 名
            draw.text((x + 6, y + 6), slot["slot"], fill="red")
        print(f"{meme['name']}：{len(slots)} 个 slot")
        for s in slots:
            print(f"  {s['slot']}: x={s['x_pct']:.2f} y={s['y_pct']:.2f} "
                  f"w={s['w_pct']:.2f} h={s['h_pct']:.2f}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, f"{template_id}_slots.png")
    img.save(out_path)
    print(f"\n已保存：{out_path}")


if __name__ == "__main__":
    main()
