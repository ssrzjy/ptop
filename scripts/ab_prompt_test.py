"""S1 提示词 A/B 测试（不改动主代码，独立脚本）。

对比「修改前(旧提示词)」与「修改后(新提示词，带 core_attack 靶心 + 精确打击)」
在同一张截图、同一个固定模板下生成的文字差异。

控制变量：图片相同、模板相同、模型相同、调用路径相同，
          唯一变量 = system prompt + schema。

用法：
    ALL_PROXY=http://proxy2.intsig.net:10081 \
        .venv/bin/python scripts/ab_prompt_test.py <截图路径> <固定模板id> [gif]

示例：
    ... scripts/ab_prompt_test.py ~/Downloads/chat.jpg 286126573
    ... scripts/ab_prompt_test.py ~/Downloads/chat.jpg 222516354 gif

产出：
    output/ab_old.<png|gif>   旧提示词生成的图
    output/ab_new.<png|gif>   新提示词生成的图
    终端并列打印两版的 core_attack(仅新版有) 与 captions。
"""

import os
import sys
import json
import base64

# 让脚本从任意目录运行都能找到 src/：把项目根目录加入搜索路径
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# 复用主代码，不做任何修改
from src.config import get_model
from src.llm import get_client
from src.meme_fetcher import meme_list_for_prompt
from src.nodes.s1_understand import (
    _detect_mime,
    _build_system_prompt,      # 新版提示词（当前代码）
    COMBINED_SCHEMA,           # 新版 schema（含 core_attack）
)
from src.nodes.s6_compose import compose, _find_template_path


# ============================================================
# 旧版（修改前）提示词 + schema —— 内置快照，用于对照
# ============================================================
def _build_old_prompt(media_type: str = "img") -> str:
    meme_list = meme_list_for_prompt(media_type)
    return (
        "你是分析聊天截图并生成反PUA梗图文案的助手。\n"
        "1. 看懂截图，识别是否存在PUA/职场压迫/道德绑架等行为，填写 pua_type。\n"
        "2. 若内容涉及违法/未成年人/极端暴力，设 blocked=true，template_id 和 captions 留空。\n"
        "3. 否则：\n"
        "   a. 从下方梗图列表中选一个最贴合当前情绪和回怼语义的模板，填写 template_id。\n"
        "   b. 针对截图里的具体内容，生成两条有杀伤力的配文（每条≤15字）：\n"
        "      - 配文必须紧扣截图中的实际言行，不要泛泛而谈\n"
        "      - 目标是让看到的人觉得又准又狠又好笑\n"
        "      - slot=top 和 slot=bottom 形成对比或反转，具体形式不限\n\n"
        "梗图列表（格式：id|名称）：\n"
        f"{meme_list}\n\n"
        "只输出符合给定 JSON schema 的结果，不要多余文字。"
    )


OLD_SCHEMA = {
    "type": "object",
    "properties": {
        "pua_type": {"type": "string"},
        "blocked": {"type": "boolean"},
        "template_id": {"type": "string"},
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["slot", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["pua_type", "blocked", "template_id", "captions"],
    "additionalProperties": False,
}


def _run_model(system_prompt: str, schema: dict, image_b64: str) -> dict:
    """唯一变量 = system_prompt + schema，其余调用路径与 S1 完全一致。"""
    cfg = get_model("s1_understand")
    client = get_client(cfg)

    content = [{"type": "text", "text": "分析这张聊天截图，按 schema 输出结果。"}]
    if image_b64:
        mime = _detect_mime(image_b64)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
        })

    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "context", "schema": schema},
        },
    )
    raw = (resp.choices[0].message.content or "").strip()
    # 剥掉可能的 markdown fence
    if raw.startswith("```"):
        lines = raw.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        raw = "\n".join(lines[1:end])
    return json.loads(raw)


def _compose_with_fixed_template(
    captions: list, template_id: str, media_type: str, tag: str
) -> str:
    """用指定模板 + 给定 captions 合成一张图，返回带 tag 的输出路径。
    复用 s6_compose.compose，通过构造 state 强制指定模板。"""
    state = {
        "context": {"template_id": template_id, "captions": captions},
        "media_type": media_type,
        "status": "running",
    }
    result = compose(state)
    src_path = result["final_image"]
    # compose 按 template_id 命名，两版会同名覆盖 → 重命名区分
    ext = os.path.splitext(src_path)[-1]
    dst_path = os.path.join(os.path.dirname(src_path), f"ab_{tag}{ext}")
    os.replace(src_path, dst_path)
    return dst_path


def _print_result(tag: str, ctx: dict) -> None:
    print(f"\n【{tag}】")
    if "core_attack" in ctx:
        print(f"  靶心 core_attack: {ctx.get('core_attack')}")
    print(f"  pua_type: {ctx.get('pua_type')}")
    for cap in ctx.get("captions", []):
        print(f"  [{cap.get('slot'):>6}] {cap.get('text')}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print("用法：python scripts/ab_prompt_test.py <截图路径> <固定模板id> [gif]")
        sys.exit(1)

    media_type = "gif" if "gif" in args else "img"
    positional = [a for a in args if a != "gif"]
    image_path, template_id = positional[0], positional[1]

    # 校验固定模板存在
    if not _find_template_path(template_id, media_type):
        print(f"✗ 模板 id '{template_id}' 在 templates/{media_type}/ 下不存在")
        sys.exit(1)

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    print("=" * 50)
    print(f"截图: {image_path}")
    print(f"固定模板: {template_id}  ({media_type})")
    print("=" * 50)

    # —— 旧版 ——
    print("\n>>> 跑【旧提示词】...")
    old_ctx = _run_model(_build_old_prompt(media_type), OLD_SCHEMA, image_b64)
    _print_result("旧提示词", old_ctx)
    old_img = _compose_with_fixed_template(
        old_ctx.get("captions", []), template_id, media_type, "old"
    )

    # —— 新版 ——
    print("\n>>> 跑【新提示词】...")
    new_ctx = _run_model(_build_system_prompt(media_type), COMBINED_SCHEMA, image_b64)
    _print_result("新提示词", new_ctx)
    new_img = _compose_with_fixed_template(
        new_ctx.get("captions", []), template_id, media_type, "new"
    )

    print("\n" + "=" * 50)
    print(f"旧版出图: {old_img}")
    print(f"新版出图: {new_img}")
    print("=" * 50)
    print("并列打开两张图肉眼对比即可。")


if __name__ == "__main__":
    main()
