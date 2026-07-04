"""从 gif.json 批量下载 gif/mp4 资源到 templates/gif/"""
# pip install httpx[socks] -q
# python3 download_gifs.py
import json
import os
import sys
import time

import httpx

GIF_JSON = "gif.json"
OUT_DIR = "templates/gif"


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
    with open(GIF_JSON, encoding="utf-8") as f:
        memes = json.load(f)["data"]["memes"]

    os.makedirs(OUT_DIR, exist_ok=True)

    total = len(memes)
    ok = skip = fail = 0

    with make_client() as client:
        for i, meme in enumerate(memes, 1):
            mid = meme["id"]
            url = meme["url"]
            name = meme["name"]
            ext = os.path.splitext(url)[-1] or ".mp4"
            dest = os.path.join(OUT_DIR, f"{mid}{ext}")

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

            time.sleep(0.1)

    print(f"\n完成：成功 {ok}，跳过 {skip}，失败 {fail}，共 {total} 个")


if __name__ == "__main__":
    main()
