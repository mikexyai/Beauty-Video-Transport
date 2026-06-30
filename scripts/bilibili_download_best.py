from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COOKIE_PATH = PROJECT_ROOT / "downloads" / "bilibili" / "bilibili-cookies.txt"


def build_bilibili_ytdlp_args(
    bvid_or_url: str,
    output_path: Path,
    *,
    cookies_path: Path = DEFAULT_COOKIE_PATH,
    merge_format: str = "mp4",
) -> list[str]:
    url = bvid_or_url if bvid_or_url.startswith("http") else f"https://www.bilibili.com/video/{bvid_or_url}/"
    return [
        "python",
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--force-overwrites",
        "--cookies",
        str(cookies_path),
        "-f",
        "bestvideo*+bestaudio/best",
        "--format-sort",
        "res:2160,fps,br,codec:h265,hdr:12",
        "--merge-output-format",
        merge_format,
        "-o",
        str(output_path),
        url,
    ]


def download_bilibili_best(bvid_or_url: str, output_path: Path, *, cookies_path: Path = DEFAULT_COOKIE_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_bilibili_ytdlp_args(bvid_or_url, output_path, cookies_path=cookies_path)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").splitlines()[-20:])
        raise RuntimeError(f"Bilibili yt-dlp failed with exit {proc.returncode}: {tail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a Bilibili video at the best available quality using yt-dlp.")
    parser.add_argument("bvid_or_url")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cookies", type=Path, default=DEFAULT_COOKIE_PATH)
    parser.add_argument("--print-command", action="store_true")
    args = parser.parse_args()
    cmd = build_bilibili_ytdlp_args(args.bvid_or_url, args.out, cookies_path=args.cookies)
    if args.print_command:
        print(" ".join(cmd))
        return 0
    download_bilibili_best(args.bvid_or_url, args.out, cookies_path=args.cookies)
    print({"downloaded": str(args.out)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
