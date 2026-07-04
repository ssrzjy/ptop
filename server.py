"""HTTP 服务入口。

uvicorn server:app --host 0.0.0.0 --port 8000
"""

import base64
import mimetypes
import os

from fastapi import FastAPI
from pydantic import BaseModel

from src.graph import app as graph_app

_THREAD_ID = "server-thread"

server = FastAPI()


class GenerateRequest(BaseModel):
    image_b64: str
    media_type: str = "img"


class GenerateResponse(BaseModel):
    data: str
    tag: str


def _strip_prefix(b64: str) -> str:
    """兼容带 data:image/...;base64, 前缀和裸 base64 两种格式。"""
    if "," in b64:
        return b64.split(",", 1)[1]
    return b64


def _file_to_data_uri(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        mime = "image/png"
    with open(path, "rb") as f:
        encoded = base64.standard_b64encode(f.read()).decode()
    return f"data:{mime};base64,{encoded}"


@server.get("/health")
def health():
    return {"status": "ok"}


@server.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    initial = {
        "image_b64": _strip_prefix(req.image_b64),
        "media_type": req.media_type if req.media_type in ("img", "gif") else "img",
    }
    config = {"configurable": {"thread_id": _THREAD_ID}}

    for _ in graph_app.stream(initial, config=config):
        pass

    state = graph_app.get_state(config).values
    context = state.get("context") or {}
    tag = context.get("tag", "")

    if state.get("blocked"):
        return GenerateResponse(data="", tag=tag)

    final_image: str = state.get("final_image", "")
    if not final_image or not os.path.exists(final_image):
        return GenerateResponse(data="", tag=tag)

    return GenerateResponse(data=_file_to_data_uri(final_image), tag=tag)
