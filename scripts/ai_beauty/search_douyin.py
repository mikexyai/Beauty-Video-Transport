from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any

import sys

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import PROJECT_ROOT
from scripts.ai_beauty.repositories.candidates import DEFAULT_CANDIDATE_REPOSITORY

COOKIE_PATH = PROJECT_ROOT / "config" / "douyin_ai_beauty_cookies.txt"
SEARCH_URL = "https://www.douyin.com/aweme/v1/web/general/search/single/"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"


def build_search_query(*, keyword: str, offset: int = 0, count: int = 20) -> dict[str, str]:
    return {
        "keyword": keyword,
        "search_channel": "aweme_video_web",
        "sort_type": "0",
        "publish_time": "0",
        "offset": str(offset),
        "count": str(count),
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "pc_client_type": "1",
        "version_code": "170400",
        "version_name": "17.4.0",
        "cookie_enabled": "true",
        "screen_width": "1920",
        "screen_height": "1080",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Chrome",
        "browser_version": "149.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "engine_version": "149.0.0.0",
        "os_name": "Windows",
        "os_version": "10",
        "cpu_core_num": "16",
        "device_memory": "8",
        "platform": "PC",
    }


def extract_hashtags(aweme: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for item in aweme.get("text_extra") or []:
        tag = item.get("hashtag_name") or item.get("hashtag_id")
        if tag:
            tags.append(str(tag))
    return tags


def extract_aweme_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in payload.get("data") or []:
        aweme = item.get("aweme_info") or item.get("aweme") or item
        if not isinstance(aweme, dict):
            continue
        aweme_id = str(aweme.get("aweme_id") or aweme.get("awemeId") or "").strip()
        if not aweme_id.isdigit():
            continue
        author = aweme.get("author") or {}
        stats = aweme.get("statistics") or aweme.get("stats") or {}
        video = aweme.get("video") or {}
        duration_ms = aweme.get("duration")
        duration_seconds = None
        if isinstance(duration_ms, (int, float)):
            duration_seconds = float(duration_ms) / 1000 if duration_ms > 1000 else float(duration_ms)
        candidates.append({
            "aweme_id": aweme_id,
            "douyin_url": f"https://www.douyin.com/video/{aweme_id}",
            "caption": aweme.get("desc") or aweme.get("caption") or "",
            "author_id": str(author.get("uid") or author.get("sec_uid") or author.get("short_id") or "") or None,
            "author_name": author.get("nickname") or author.get("unique_id") or author.get("short_id"),
            "hashtags": extract_hashtags(aweme),
            "duration_seconds": duration_seconds,
            "width": video.get("width"),
            "height": video.get("height"),
            "source_stats": stats,
        })
    return candidates


def validate_douyin_search_payload(payload: dict[str, Any]) -> None:
    """Raise on Douyin API blocker responses that should not look like zero candidates."""
    status_code = payload.get("status_code")
    if status_code in (None, 0):
        return
    status_msg = str(payload.get("status_msg") or payload.get("message") or "")
    if status_code == 2483 or "请先登录" in status_msg or "登录" in status_msg:
        raise RuntimeError(f"Douyin search login required (status_code={status_code}, status_msg={status_msg})")
    raise RuntimeError(f"Douyin search API error (status_code={status_code}, status_msg={status_msg})")


def search_douyin(keyword: str, *, offset: int = 0, count: int = 20, cookie_path: Path = COOKIE_PATH) -> dict[str, Any]:
    if not cookie_path.exists():
        raise FileNotFoundError(
            f"Douyin cookie file not found: {cookie_path}. "
            "Create a dedicated AI Beauty cookie jar via refresh_douyin_cookies.py, "
            "a configured parser/API, or controlled read-only CDP export."
        )
    jar = MozillaCookieJar(str(cookie_path))
    jar.load(ignore_discard=True, ignore_expires=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    query = build_search_query(keyword=keyword, offset=offset, count=count)
    url = SEARCH_URL + "?" + urllib.parse.urlencode(query)
    headers = {
        "User-Agent": DEFAULT_UA,
        "Referer": f"https://www.douyin.com/search/{urllib.parse.quote(keyword)}?type=video",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Origin": "https://www.douyin.com",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=30) as resp:
        raw = resp.read()
    if not raw:
        raise RuntimeError("Douyin search returned empty response body")
    payload = json.loads(raw.decode("utf-8"))
    validate_douyin_search_payload(payload)
    return {
        "payload": payload,
        "candidates": extract_aweme_candidates(payload),
        "has_more": payload.get("has_more"),
        "cursor": payload.get("cursor"),
        "response_bytes": len(raw),
    }


def filter_storeable_candidates(candidates: list[dict[str, Any]], *, excluded_aweme_ids: set[str] | None = None) -> list[dict[str, Any]]:
    return DEFAULT_CANDIDATE_REPOSITORY.filter_storeable_candidates(candidates, excluded_aweme_ids=excluded_aweme_ids)


def fetch_non_storeable_aweme_ids(candidate_ids: list[str]) -> set[str]:
    return DEFAULT_CANDIDATE_REPOSITORY.fetch_non_storeable_aweme_ids(candidate_ids)


def upsert_search_candidates(candidates: list[dict[str, Any]], *, keyword: str, run_id: str | None = None) -> int:
    return DEFAULT_CANDIDATE_REPOSITORY.upsert_search_candidates(candidates, keyword=keyword, run_id=run_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search Douyin videos without CDP and upsert AI Beauty candidates.")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = search_douyin(args.keyword, offset=args.offset, count=args.count)
    if args.dry_run:
        out = {k: v for k, v in result.items() if k != "payload"}
        out["sample"] = result["candidates"][:5]
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        return 0
    run_id = f"search:{args.keyword}:{args.offset}"
    inserted = upsert_search_candidates(result["candidates"], keyword=args.keyword, run_id=run_id)
    out = {"keyword": args.keyword, "offset": args.offset, "count": args.count, "found": len(result["candidates"]), "inserted_or_updated": inserted, "has_more": result.get("has_more"), "cursor": result.get("cursor"), "response_bytes": result.get("response_bytes")}
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0 if inserted else 1


if __name__ == "__main__":
    raise SystemExit(main())
