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


# 分离超时：连接 15s，单次读取 60s（大文件按分块读取，每块不超时即可），
# 写入 15s，连接池等待 15s。比单一 timeout=20 更适合 gif/mp4。
TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=15.0)
MAX_RETRIES = 3


def make_client() -> httpx.Client:
    proxy = os.environ.get("ALL_PROXY") or os.environ.get("all_proxy") or ""
    if proxy:
        proxy = fix_proxy(proxy)
        print(f"使用代理: {proxy}")
        return httpx.Client(proxy=proxy, timeout=TIMEOUT, follow_redirects=True)
    return httpx.Client(timeout=TIMEOUT, follow_redirects=True)


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

            tmp = dest + ".part"
            success = False
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    # 流式下载：分块写入，避免大文件一次性载入内存，
                    # 也避免整体读取撞上超时。
                    size = 0
                    with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with open(tmp, "wb") as f:
                            for chunk in resp.iter_bytes(chunk_size=65536):
                                f.write(chunk)
                                size += len(chunk)
                    os.replace(tmp, dest)  # 下载完整后才落到最终文件名
                    print(f"[{i}/{total}] ✓ {mid} {name} ({size // 1024}KB)")
                    ok += 1
                    success = True
                    break
                except Exception as e:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    if attempt < MAX_RETRIES:
                        wait = 2 ** attempt  # 退避：2s, 4s
                        print(
                            f"[{i}/{total}] ⚠ {mid} {name} 第{attempt}次失败，"
                            f"{wait}s 后重试 — {e}",
                            file=sys.stderr,
                        )
                        time.sleep(wait)
                    else:
                        print(
                            f"[{i}/{total}] ✗ {mid} {name} 重试{MAX_RETRIES}次仍失败 — {e}",
                            file=sys.stderr,
                        )
            if not success:
                fail += 1

            time.sleep(0.1)

    print(f"\n完成：成功 {ok}，跳过 {skip}，失败 {fail}，共 {total} 个")


if __name__ == "__main__":
    main()
