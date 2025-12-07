#!/usr/bin/env python3
import json
import os
import sys
from typing import Optional

from playwright.sync_api import sync_playwright


# Streamlink'in çözemediği kanallar
SPECIAL_CHANNELS = [
    {
        "name": "TRT 2",
        "slug": "trt2",
        "url": "https://www.tabii.com/en/watch/live/trt2",
    },
    {
        "name": "TRT ÇOCUK",
        "slug": "trtcocuk",
        "url": "https://www.tabii.com/watch/live/trtcocuk",
    },
    {
        "name": "TRT AVAZ",
        "slug": "trtavaz",
        "url": "https://www.tabii.com/en/watch/live/trtavaz",
    },
    {
        "name": "TV8,5",
        "slug": "tv8bucuk",
        "url": "https://www.tv8bucuk.com/tv8-5-canli-yayin",
    },
]


def load_output_paths(config_path: str = "config.json"):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    out = config.get("output", {})
    root_name = out.get("folder", "streams")
    best_name = out.get("bestFolder", "best")
    master_name = out.get("masterFolder", "")

    cwd = os.getcwd()
    root_folder = os.path.join(cwd, root_name)

    # masterFolder boşsa master'ları root'a yaz
    if master_name:
        master_folder = os.path.join(root_folder, master_name)
    else:
        master_folder = root_folder

    best_folder = os.path.join(root_folder, best_name)

    os.makedirs(root_folder, exist_ok=True)
    os.makedirs(best_folder, exist_ok=True)
    if master_folder != root_folder:
        os.makedirs(master_folder, exist_ok=True)

    return root_folder, master_folder, best_folder


def find_m3u8_url(page_url: str, timeout_ms: int = 20000) -> Optional[str]:
    """
    Playwright ile sayfayı açar, network isteklerinden ilk .m3u8 URL'sini yakalar.
    """
    print(f"  [*] Opening page: {page_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        found = {"url": None}

        def on_request(request):
            url = request.url
            if ".m3u8" in url:
                # Basit filtre: reklam vb. istemiyorsan burada ekleyebilirsin
                if not found["url"]:
                    found["url"] = url
                    print(f"  [*] Found m3u8 request: {url}")

        context.on("request", on_request)

        try:
            page.goto(page_url, wait_until="networkidle", timeout=timeout_ms)
        except Exception as e:
            print(f"  [!] goto error: {e}")

        # Biraz daha bekle, geç gelen istekleri yakalamak için
        for _ in range(20):
            if found["url"]:
                break
            page.wait_for_timeout(500)  # 0.5 sn

        browser.close()
        return found["url"]


def write_simple_playlist(master_folder: str, best_folder: str, slug: str, m3u8_url: str):
    """
    Bulduğumuz tek bir m3u8 URL'sinden basit bir playlist üretir:
    #EXTM3U
    <m3u8_url>
    """
    text = "#EXTM3U\n" + m3u8_url + "\n"

    master_path = os.path.join(master_folder, f"{slug}.m3u8")
    best_path = os.path.join(best_folder, f"{slug}.m3u8")

    with open(master_path, "w", encoding="utf-8") as f:
        f.write(text)

    with open(best_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"  [+] Wrote playlists: {master_path}, {best_path}")


def main():
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    print(f"=== Tabii/TV8.5 scraper starting (config: {config_file}) ===")

    root_folder, master_folder, best_folder = load_output_paths(config_file)
    print(f"Output folders:")
    print(f"  Root  : {root_folder}")
    print(f"  Master: {master_folder}")
    print(f"  Best  : {best_folder}")
    print()

    success = 0
    fail = 0

    for ch in SPECIAL_CHANNELS:
        name = ch["name"]
        slug = ch["slug"]
        url = ch["url"]

        print(f"[*] Channel: {name} ({slug})")
        print(f"    URL: {url}")

        try:
            m3u8_url = find_m3u8_url(url)
            if not m3u8_url:
                print("  [!] No .m3u8 URL found.")
                fail += 1
                continue

            write_simple_playlist(master_folder, best_folder, slug, m3u8_url)
            success += 1

        except Exception as e:
            print(f"  [!] Error: {e}")
            fail += 1

        print()

    print("=== Tabii/TV8.5 scraper summary ===")
    print(f"  Successful: {success}")
    print(f"  Failed    : {fail}")
    print(f"  Total     : {len(SPECIAL_CHANNELS)}")


if __name__ == "__main__":
    main()
