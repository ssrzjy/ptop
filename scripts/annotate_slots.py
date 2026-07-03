"""批量分析梗图模板，识别文字留白区域坐标，写回 meta.json。

用法：
    python scripts/annotate_slots.py

- 已有 slots 字段的条目自动跳过，支持断点续跑
- 坐标用百分比存储，与图片尺寸无关
- 没有留白区域的梗图写入 slots=[]，S6 降级贴顶底
"""

import os
import sys
import json
import base64
import glob

# 把项目根目录加入 path，复用 src/config 和 src/llm
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import get_model
from src.llm import get_client

META_PATH = "meta.json"
TEMPLATES_DIR = "templates"

SLOT_SCHEMA = {
    "type": "object",
    "properties": {
        "slots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot":  {"type": "string"},  # "box_0" / "box_1" ...
                    "x_pct": {"type": "number"},  # 左边距 / 图宽，0~1
                    "y_pct": {"type": "number"},  # 上边距 / 图高，0~1
                    "w_pct": {"type": "number"},  # 区域宽 / 图宽，0~1
                    "h_pct": {"type": "number"},  # 区域高 / 图高，0~1
                },
                "required": ["slot", "x_pct", "y_pct", "w_pct", "h_pct"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["slots"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "你是梗图版式分析助手。观察图片，找出专门留给配文的空白矩形区域。\n"
    "这类区域通常是纯白/纯色的空白格，位于图片的边缘或分隔带，"
    "不包含任何人物、表情或主体内容。\n"
    "按从上到下、从左到右的顺序，用 box_0/box_1/box_2... 命名每个区域，"
    "坐标均为占图片宽高的比例（0~1 之间的小数，保留两位）。\n"
    "如果图片没有明显的配文留白区域（整张图都是内容），返回空数组。\n"
    "只输出符合 JSON schema 的结果，不要多余文字。"
)


def encode_image(path: str) -> tuple[str, str]:
    """返回 (base64, mime_type)。"""
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.standard_b64encode(data).decode()
    if data[:4] == b"\x89PNG":
        mime = "image/png"
    elif data[:2] == b"\xff\xd8":
        mime = "image/jpeg"
    else:
        mime = "image/jpeg"
    return b64, mime


def find_local_path(template_id: str) -> str | None:
    matches = glob.glob(os.path.join(TEMPLATES_DIR, f"{template_id}.*"))
    return matches[0] if matches else None


def annotate(client, cfg, template_id: str, local_path: str, box_count: int = 0) -> list[dict]:
    b64, mime = encode_image(local_path)
    if box_count > 0:
        user_text = (
            f"这张梗图有 {box_count} 个标准配文区域，"
            f"请找出恰好 {box_count} 个纯白/纯色留白矩形，输出坐标。"
        )
    else:
        user_text = "分析这张梗图，输出文字留白区域坐标。"

    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "slots", "schema": SLOT_SCHEMA},
        },
    )
    result = json.loads(resp.choices[0].message.content)
    slots = result.get("slots", [])
    # 超出 box_count 的多余 slot 截断，防止模型仍然多输出
    if box_count > 0 and len(slots) > box_count:
        slots = slots[:box_count]
    return slots


def main() -> None:
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    memes = meta["data"]["memes"]
    cfg = get_model("s1_understand")
    client = get_client(cfg)

    total = len(memes)
    ok = skip = fail = 0

    for i, meme in enumerate(memes, 1):
        mid = meme["id"]
        name = meme["name"]

        if "slots" in meme:
            print(f"[{i}/{total}] 跳过（已标注）{mid} {name}")
            skip += 1
            continue

        local_path = find_local_path(mid)
        if not local_path:
            print(f"[{i}/{total}] 跳过（无本地文件）{mid} {name}")
            skip += 1
            continue

        try:
            slots = annotate(client, cfg, mid, local_path, meme.get("box_count", 0))
            meme["slots"] = slots
            label = f"{len(slots)} 个区域" if slots else "无留白"
            print(f"[{i}/{total}] ✓ {mid} {name} — {label}")
            ok += 1
        except Exception as e:
            print(f"[{i}/{total}] ✗ {mid} {name} — {e}", file=sys.stderr)
            fail += 1

        # 每处理 10 张保存一次，防止中途崩溃丢失进度
        if i % 10 == 0:
            with open(META_PATH, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n完成：标注 {ok}，跳过 {skip}，失败 {fail}，共 {total} 张")


if __name__ == "__main__":
    main()
