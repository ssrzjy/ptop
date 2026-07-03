"""S0 预处理 / 隐私脱敏。

职责:马赛克人脸和手机号等敏感信息,把图缩放到长边 <= 2576px
(Claude Opus 4.8 视觉上限),转成 base64。

MVP 桩:直接透传。真实实现建议放在客户端上传前完成。
"""

from src.state import MemeState


def preprocess(state: MemeState) -> dict:
    # TODO: 脱敏 + 缩放 + base64 编码
    return {
        "status": "running",
        "blocked": False,
        "retry_count": 0,
        # image_b64 假设由入口已注入;此处只做占位
        "image_b64": state.get("image_b64", ""),
    }
