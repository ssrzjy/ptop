"""一次性预下载 meta.json 里的所有梗图到 templates/。

用法：
    python scripts/download_memes.py
"""

import os
import sys
import json
import time

import httpx

META_PATH = "meta.json"
TEMPLATES_DIR = "templates"


def fix_proxy(url: str) -> str:
    if url.startswith("socks://"):
        return "socks5://" + url[len("socks://"):]
    return url


def make_client() -> httpx.Client:
    proxy = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy") or ""
    if proxy:
        proxy = fix_proxy(proxy)
        print(f"使用代理: {proxy}")
        return httpx.Client(proxy=proxy, timeout=20)
    return httpx.Client(timeout=20)


def main() -> None:
    with open(META_PATH, encoding="utf-8") as f:
        memes = json.load(f)["data"]["memes"]

    os.makedirs(TEMPLATES_DIR, exist_ok=True)

    total = len(memes)
    ok = skip = fail = 0

    with make_client() as client:
        for i, meme in enumerate(memes, 1):
            mid = meme["id"]
            url = meme["url"]
            name = meme["name"]
            ext = os.path.splitext(url)[-1] or ".jpg"
            dest = os.path.join(TEMPLATES_DIR, f"{mid}{ext}")

            if os.path.exists(dest):
                print(f"[{i}/{total}] 跳过（已存在）{mid} {name}")
                skip += 1
                continue

            try:
                resp = client.get(url)
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    f.write(resp.content)
                size_kb = len(resp.content) // 1024
                print(f"[{i}/{total}] ✓ {mid} {name} ({size_kb}KB)")
                ok += 1
            except Exception as e:
                print(f"[{i}/{total}] ✗ {mid} {name} — {e}", file=sys.stderr)
                fail += 1

            time.sleep(0.1)  # 避免请求过快被限速

    print(f"\n完成：成功 {ok}，跳过 {skip}，失败 {fail}，共 {total} 张")


if __name__ == "__main__":
    main()
