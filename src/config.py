"""模型配置 —— 按阶段各自指定用哪个模型。

设计目标:
  1. 换模型只改这一处;每个调模型的阶段独立配置。
  2. 一个统一 key,靠不同 base_url 路由到不同模型 —— key 共用,
     base_url + model 每个阶段各自配。

读取优先级:环境变量 > 这里的默认值。
  S1_MODEL / S1_BASE_URL / S4_MODEL / S4_BASE_URL 等可用环境变量覆盖。
  统一 key 走环境变量(默认 API_KEY),写在项目根目录的 .env 里(见 .env.example)。
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# 启动时自动加载项目根目录的 .env(不覆盖已存在的真实环境变量)
load_dotenv()


@dataclass(frozen=True)
class ModelConfig:
    provider: str          # "anthropic" / "openai" / "google" / ... 之后再定
    model: str             # 模型 ID(网关上的名字)
    base_url: str          # 该阶段模型对应的接口地址(靠它路由到不同模型)
    api_key_env: str       # 去哪个环境变量取统一 key

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"缺少环境变量 {self.api_key_env}:请在 .env 或环境里配置该 key"
            )
        return key


# 统一 key 的环境变量名(一个 key 全阶段共用)
API_KEY_ENV = "API_KEY"

# --- 各阶段的模型:改这里,或用环境变量覆盖 ---
STAGE_MODELS: dict[str, ModelConfig] = {
    # S1 识图:视觉模型
    "s1_understand": ModelConfig(
        provider=os.environ.get("S1_PROVIDER", "openai"),
        model=os.environ.get("S1_MODEL", "doubao-seed-1.6-flash"),
        base_url=os.environ.get("S1_BASE_URL", ""),
        api_key_env=API_KEY_ENV,
    ),
    # S4 文案生成:同一个 key,不同 base_url -> 路由到另一个模型
    "s4_generate": ModelConfig(
        provider=os.environ.get("S4_PROVIDER", "openai"),
        model=os.environ.get("S4_MODEL", "doubao-seed-1.6-flash"),
        base_url=os.environ.get("S4_BASE_URL", ""),
        api_key_env=API_KEY_ENV,
    ),
}


def get_model(stage: str) -> ModelConfig:
    """节点用它拿自己阶段的模型配置。"""
    return STAGE_MODELS[stage]
