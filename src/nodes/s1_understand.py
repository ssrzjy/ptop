"""S1 视觉理解 + 文案生成 —— 合并为单次模型调用。

一次调用完成：
  1. 看懂截图，识别 pua_type
  2. 直接生成贴到梗图上的 captions（top/bottom，≤15字）
  3. 判断是否越界（blocked），省掉单独的安全节点调用
"""

import json
import base64

from src.state import MemeState
from src.config import get_model
from src.llm import get_client
from src.meme_fetcher import meme_list_for_prompt

COMBINED_SCHEMA = {
    "type": "object",
    "properties": {
        "tag": {"type": "string"},         # 图片主题标签,模型自由概括,如 "职场加班" / "情感冷暴力" / "催婚"
        "pua_type": {"type": "string"},    # "职场PUA" / "情感PUA" / "道德绑架" / "无"
        "blocked": {"type": "boolean"},    # 违法/极端内容时为 true
        # core_attack 放在 captions 之前：先逼模型锁定“打击靶心”，
        # 后续 captions 的生成会以它为条件，从而做到精确反击而非泛泛而谈。
        "core_attack": {"type": "string"},  # 对方最核心的一句PUA话术/攻击逻辑（原话或概括）
        "template_id": {"type": "string"}, # 从梗图列表中选一个 id
        "captions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # 只允许 top/bottom，和 compose 的放置逻辑一一对应
                    "slot": {"type": "string", "enum": ["top", "bottom"]},
                    "text": {"type": "string"},  # ≤15字
                },
                "required": ["slot", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tag", "pua_type", "blocked", "core_attack", "template_id", "captions"],
    "additionalProperties": False,
}


def _build_system_prompt(media_type: str = "img") -> str:
    meme_list = meme_list_for_prompt(media_type)
    return (
        "你是分析聊天截图并生成反PUA梗图文案的助手。\n"
        "0. 用一个简短词概括这张图的主题场景（如\"职场加班\"/\"情感冷暴力\"/\"催婚\"），填入 tag。\n"
        "1. 看懂截图，识别是否存在PUA/职场压迫/道德绑架等行为，填写 pua_type。\n"
        "2. 若内容涉及违法/未成年人/极端暴力，设 blocked=true，其余字段留空。\n"
        "3. 否则，按以下顺序思考并输出：\n"
        "\n"
        "   【第一步 · 锁定靶心】先填 core_attack：\n"
        "   通读截图，找出对方最核心、最具操控性的那**一句**话术或逻辑，\n"
        "   用原话或一句话概括。这是你后面要精确反击的唯一靶子。\n"
        "   例：\"不加班就是不上进\" / \"我这都是为你好\" / \"这点事都做不好\"。\n"
        "\n"
        "   【第二步 · 选图】填 template_id：\n"
        "   从下方梗图列表选一个最贴合反击情绪的模板。\n"
        "\n"
        "   【第三步 · 精确打击】生成 captions，最多两条（每条≤15字）：\n"
        "   目标：让对方哑口无言，读者看了拍手叫好。宁可锋利，不要礼貌。\n"
        "\n"
        "   配文必须**直接拆解 core_attack 这一句**，从下面挑一种最狠的打法：\n"
        "   - 【以子之矛】把对方的逻辑原样套回他自己身上，让他自相矛盾。\n"
        "     例 core_attack=\"这点事都做不好\" → \"这点话你也好意思说出口\"。\n"
        "   - 【戳破双标】指出他对别人和对自己用两套标准。\n"
        "     例 core_attack=\"年轻人就该多吃苦\" → \"那你年轻时的苦呢\"。\n"
        "   - 【拆穿话术】直接点名这就是PUA/道德绑架，撕掉\"为你好\"的包装。\n"
        "     例 core_attack=\"我这都是为你好\" → \"为我好就别PUA我\"。\n"
        "   - 【反问到底】用一句反问把他的荒谬前提顶回去，不接他的话。\n"
        "     例 core_attack=\"不加班就是不上进\" → \"加你的班关我的命\"。\n"
        "\n"
        "   硬性要求：\n"
        "   - 一针见血，短句、口语、有攻击性，像真人怼架，别端着。\n"
        "   - 读者看到配文，应能立刻对应上截图里对方说的那句话。\n"
        "   - 严禁万能句（如\"关我什么事\"\"你说得对呢\"），也严禁\"讲道理式\"\n"
        "     的解释和说教，必须是一句能噎住对方的话。\n"
        "   - 【重要】captions 里只能出现\"我方的回怼话\"，绝对不要复述、\n"
        "     引用、照搬截图里对方说的原话或原文字。core_attack 只是你内部\n"
        "     分析用的靶心，绝不能把它（或它的原文）当成一条 caption 贴到图上。\n"
        "   - 优先只输出 1 条 slot=bottom 的回怼话，让这句话单独拿出来也\n"
        "     成立、能一击致命。确需 2 条时，top 和 bottom 都必须是我方的\n"
        "     回怼话（可以是递进或补刀），而不是对方的原话。\n"
        "   - 反例（力度不够，禁止）：core_attack=\"我这都是为你好\"\n"
        "     → \"谢谢你的关心\"（软了）；\n"
        "     正例 → \"为我好就别替我做主\"（怼到点上）。\n"
        "\n"
        "梗图列表（格式：id|名称）：\n"
        f"{meme_list}\n\n"
        "只输出符合给定 JSON schema 的结果，不要多余文字。"
    )


def _detect_mime(image_b64: str) -> str:
    head = base64.b64decode(image_b64[:16])
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return "image/png"


def understand(state: MemeState) -> dict:
    cfg = get_model("s1_understand")
    client = get_client(cfg)
    media_type = state.get("media_type", "img")

    image_b64 = state.get("image_b64", "")
    content = [
        {"type": "text", "text": "分析这张聊天截图，按 schema 输出结果。"},
    ]
    if image_b64:
        mime = _detect_mime(image_b64)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_b64}"},
        })

    resp = client.chat.completions.create(
        model=cfg.model,
        messages=[
            {"role": "system", "content": _build_system_prompt(media_type)},
            {"role": "user", "content": content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "context", "schema": COMBINED_SCHEMA},
        },
    )

    choice = resp.choices[0]
    raw = choice.message.content or ""
    print(f"  [S1] finish_reason={choice.finish_reason} content_len={len(raw)}")

    if not raw.strip():
        print(f"  [S1] 模型返回空内容，按 blocked 处理")
        return {
            "context": {"tag": "", "pua_type": "unknown", "blocked": True, "template_id": "", "captions": []},
            "blocked": True,
        }

    # 剥掉模型可能包裹的 markdown fence（```json ... ```）
    stripped = raw.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        end = -1 if lines[-1].strip() == "```" else len(lines)
        stripped = "\n".join(lines[1:end])

    try:
        context = json.loads(stripped)
    except Exception as e:
        print(f"  [S1] JSON 解析失败：{e}")
        return {
            "context": {"tag": "", "pua_type": "unknown", "blocked": True, "template_id": "", "captions": []},
            "blocked": True,
        }

    return {"context": context, "blocked": context.get("blocked", False)}
