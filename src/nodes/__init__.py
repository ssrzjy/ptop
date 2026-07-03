"""节点桩集合。每个节点是 (state) -> partial state 的纯函数。

真实逻辑后续打磨:
  - S1 / S4 里替换为 Claude Opus 4.8 调用(structured output)
  - S6 里替换为 Canvas / Pillow 贴字合成
"""

from .s0_preprocess import preprocess
from .s1_understand import understand
from .s2_input_safety import input_safety
from .s3_pick_style import pick_style
from .s4_generate import generate
from .s5_output_safety import output_safety
from .s6_compose import compose

__all__ = [
    "preprocess",
    "understand",
    "input_safety",
    "pick_style",
    "generate",
    "output_safety",
    "compose",
]
