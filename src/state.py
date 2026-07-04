"""贯穿整条图→图流程的全局状态。

Context JSON(S1 产出)与 Generation JSON(S4 产出)是与上下游的接口契约,
先在这里定死字段;图内节点只读改自己关心的部分。
"""

from typing import TypedDict, Optional, Literal


class MemeState(TypedDict, total=False):
    # --- S0 产出 ---
    image_b64: str                 # 脱敏 + 标准化后的截图(base64)

    # --- S1 产出:Context JSON(理解结果) ---
    context: Optional[dict]        # {tag, pua_type, blocked, template_id, captions} —— tag 为图片主题标签

    # --- S2 / S5 产出:安全判定 ---
    safety: Optional[dict]         # {is_negative, blocked, reason}

    # --- S3 产出 ---
    style: Optional[str]           # 回怼风格,如 "犀利吐槽" / "阴阳怪气" / "温和反击"

    # --- S4 产出:Generation JSON ---
    generation: Optional[dict]     # {reply_text, template_id, captions:[{slot,text}]}

    # --- S6 产出 ---
    final_image: Optional[str]     # 合成后的梗图(base64 或路径)

    # --- 控制字段 ---
    blocked: bool                  # 是否被安全拦截
    retry_count: int               # S5→S4 重写计数,防死循环
    status: Literal["running", "blocked", "done"]
    media_type: Literal["img", "gif"]  # 底图来源子目录


MAX_REWRITE = 2  # S5 不合规时回 S4 重写的最大次数
