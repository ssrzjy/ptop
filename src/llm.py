"""统一的 LLM 客户端工厂。

按 ModelConfig.provider 建对应 SDK 的 client。当前网关(火山 Ark)是
OpenAI 兼容格式,所以 provider="openai" 走 openai SDK 指向自定义 base_url。
"""

from functools import lru_cache

from openai import OpenAI

from src.config import ModelConfig


@lru_cache(maxsize=None)
def _client(provider: str, base_url: str, api_key: str) -> OpenAI:
    if provider == "openai":
        return OpenAI(api_key=api_key, base_url=base_url or None)
    raise ValueError(f"暂不支持的 provider: {provider}")


def get_client(cfg: ModelConfig) -> OpenAI:
    return _client(cfg.provider, cfg.base_url, cfg.api_key)
