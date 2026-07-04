"""梗图素材库加载。

templates/manifest.json 描述每个模板:
  {
    "模板id": {
      "file": "图片文件名.png",
      "box": [x, y, w, h],   # 贴回怼话的文字区域(左上角坐标 + 宽高)
      "fill": "white",       # 文字颜色
      "stroke": "black",     # 描边颜色
      "desc": "风格说明"      # 给 S4 选模板时看的
    }
  }

要加新梗图:把图片丢进 templates/,在 manifest.json 里加一条即可。
"""

import os
import json
from functools import lru_cache

TEMPLATES_DIR = "templates"
MANIFEST = os.path.join(TEMPLATES_DIR, "manifest.json")


@lru_cache(maxsize=1)
def list_templates() -> dict:
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def get_template(template_id: str) -> dict:
    meta = dict(list_templates()[template_id])
    meta["path"] = os.path.join(TEMPLATES_DIR, meta["file"])
    return meta


# 特殊值:表示"素材库没有合适模板,请用文生图生成背景"
GENERATE = "__generate__"


def valid_template_id(template_id: str | None) -> str:
    """校验模型给的 id:
    - 是真实模板 -> 原样返回
    - 是文生图特殊值 -> 原样返回(交给 S6 走文生图)
    - 其它非法值 -> 回退到素材库第一个
    """
    templates = list_templates()
    if template_id == GENERATE or template_id in templates:
        return template_id
    return next(iter(templates))
