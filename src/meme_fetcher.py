"""梗图元数据加载 + 本地缓存下载。

读取项目根目录的 meta.json（imgflip 格式），提供：
  - meme_list_for_prompt()：注入 S1 prompt 的紧凑列表
  - ensure_template(id, url)：下载图片到 templates/ 并返回本地路径
"""

import os
import glob
import json

import httpx

META_PATH = "meta.json"
GIF_META_PATH = "gif.json"
TEMPLATES_BASE = "templates"


def _load_meta(media_type: str = "img") -> list[dict]:
    path = GIF_META_PATH if media_type == "gif" else META_PATH
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["data"]["memes"]


def meme_list_for_prompt(media_type: str = "img") -> str:
    """返回注入 prompt 的梗图列表，格式：每行 'id|name'。"""
    return "\n".join(f"{m['id']}|{m['name']}" for m in _load_meta(media_type))


def _fix_proxy(url: str) -> str:
    """将 socks:// 修正为 socks5://，httpx 不认裸 socks:// 格式。"""
    if url.startswith("socks://"):
        return "socks5://" + url[len("socks://"):]
    return url


def _make_client() -> httpx.Client:
    proxy = (
        os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
        or ""
    )
    if proxy:
        proxy = _fix_proxy(proxy)
        return httpx.Client(proxy=proxy, timeout=15)
    return httpx.Client(timeout=15)


def ensure_template(template_id: str, url: str, media_type: str = "img") -> str:
    """确保模板图片在本地缓存，返回本地路径。有缓存直接返回，没有则下载。"""
    d = os.path.join(TEMPLATES_BASE, media_type)
    os.makedirs(d, exist_ok=True)

    cached = glob.glob(os.path.join(d, f"{template_id}.*"))
    if cached:
        return cached[0]

    ext = os.path.splitext(url)[-1] or ".jpg"
    local_path = os.path.join(d, f"{template_id}{ext}")
    with _make_client() as client:
        resp = client.get(url)
        resp.raise_for_status()
    with open(local_path, "wb") as f:
        f.write(resp.content)
    return local_path
