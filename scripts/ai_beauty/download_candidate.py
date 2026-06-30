from __future__ import annotations

import argparse
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import sys

import websocket

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import PROJECT_ROOT, connect
from scripts.ai_beauty.media import ANALYSIS_DIR, DOWNLOAD_DIR, dimensions, duration_seconds, ffprobe_json, has_video_stream, make_contact_sheet

COOKIE_PATH = PROJECT_ROOT / "config" / "douyin_ai_beauty_cookies.txt"
CDP_JSON = "http://127.0.0.1:9222/json/list"
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"


def cdp_call(ws, method: str, params: dict[str, Any] | None = None, *, msg_id: int) -> Any:
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get("id") == msg_id:
            if "error" in msg:
                raise RuntimeError(f"CDP {method} error: {msg['error']}")
            return msg.get("result")


def find_douyin_target() -> dict[str, Any]:
    data = urllib.request.urlopen(CDP_JSON, timeout=5).read().decode("utf-8", "ignore")
    targets = json.loads(data)
    pages = [t for t in targets if t.get("type") == "page" and "douyin.com" in (t.get("url") or "")]
    if not pages:
        raise RuntimeError("No open Douyin page found in Chrome CDP on 127.0.0.1:9222")
    return pages[0]


def build_cdp_detail_expression(aweme_id: str) -> str:
    return r'''
(async (awemeId) => {
  Array.from(document.querySelectorAll('video')).forEach(v => { try { v.pause(); } catch(e) {} });
  const url = `/aweme/v1/web/aweme/detail/?aweme_id=${awemeId}&device_platform=webapp&aid=6383&channel=channel_pc_web`;
  const r = await fetch(url, {credentials:'include', referrer: location.href, headers:{'accept':'application/json, text/plain, */*'}});
  const text = await r.text();
  let data = null;
  try { data = JSON.parse(text); } catch(e) {}
  return {ok:r.ok, status:r.status, text, data};
})
''' + f"({json.dumps(aweme_id)})"


def _video_from_detail(detail: dict[str, Any]) -> dict[str, Any] | None:
    aweme = detail.get("aweme_detail") or detail.get("aweme_info") or detail.get("aweme") or detail
    video = aweme.get("video") if isinstance(aweme, dict) else None
    return video if isinstance(video, dict) else None


def _addr_urls(addr: Any) -> list[str]:
    if not isinstance(addr, dict):
        return []
    return [str(u) for u in (addr.get("url_list") or []) if u]


def _best_url_from_addr(addr: dict[str, Any]) -> str | None:
    urls = _addr_urls(addr)
    if not urls:
        return None
    direct = [u for u in urls if "douyinvod.com" in u or "mime_type=video" in u or ".mp4" in u]
    pool = direct or urls
    pool.sort(key=lambda u: ("/aweme/v1/play" in u, -len(u)))
    return pool[0]


def _quality_score(*, width: Any = None, height: Any = None, fps: Any = None, bit_rate: Any = None, is_h265: Any = None, is_hdr: Any = None) -> tuple[float, float, float, float, float]:
    def num(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    w = num(width)
    h = num(height)
    pixels = w * h
    return (pixels, num(fps), num(bit_rate), 1.0 if is_hdr else 0.0, 1.0 if is_h265 else 0.0)


def _variant_from_bit_rate(item: dict[str, Any]) -> dict[str, Any] | None:
    addr = item.get("play_addr") if isinstance(item, dict) else None
    if not isinstance(addr, dict):
        return None
    url = _best_url_from_addr(addr)
    if not url:
        return None
    return {
        "url": url,
        "source": "bit_rate",
        "gear_name": item.get("gear_name"),
        "quality_type": item.get("quality_type"),
        "definition": _definition_from_extra(item.get("video_extra")),
        "width": addr.get("width"),
        "height": addr.get("height"),
        "fps": item.get("FPS"),
        "bit_rate": item.get("bit_rate"),
        "is_h265": bool(item.get("is_h265") or item.get("is_bytevc1")),
        "is_hdr": bool(item.get("HDR_type") or item.get("HDR_bit")),
        "data_size": addr.get("data_size"),
    }


def _definition_from_extra(extra: Any) -> str | None:
    if not extra:
        return None
    try:
        parsed = json.loads(extra) if isinstance(extra, str) else extra
    except Exception:
        return None
    return parsed.get("definition") if isinstance(parsed, dict) else None


def douyin_video_variants(detail: dict[str, Any]) -> list[dict[str, Any]]:
    video = _video_from_detail(detail)
    if not video:
        return []
    variants: list[dict[str, Any]] = []
    for item in video.get("bit_rate") or []:
        if isinstance(item, dict):
            variant = _variant_from_bit_rate(item)
            if variant:
                variants.append(variant)
    for key in ("play_addr", "play_addr_265", "play_addr_h264", "download_addr"):
        addr = video.get(key)
        if isinstance(addr, dict):
            url = _best_url_from_addr(addr)
            if url:
                variants.append({
                    "url": url,
                    "source": key,
                    "width": addr.get("width") or video.get("width"),
                    "height": addr.get("height") or video.get("height"),
                    "fps": None,
                    "bit_rate": None,
                    "is_h265": key == "play_addr_265" or bool(video.get("is_h265")),
                    "is_hdr": bool(video.get("is_source_HDR")),
                    "data_size": addr.get("data_size"),
                })
    # Dedupe by URL while preserving best metadata encountered first.
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for variant in variants:
        if variant["url"] in seen:
            continue
        seen.add(variant["url"])
        unique.append(variant)
    unique.sort(
        key=lambda v: _quality_score(
            width=v.get("width"),
            height=v.get("height"),
            fps=v.get("fps"),
            bit_rate=v.get("bit_rate"),
            is_h265=v.get("is_h265"),
            is_hdr=v.get("is_hdr"),
        ),
        reverse=True,
    )
    return unique


def pick_best_play_url(detail: dict[str, Any]) -> str | None:
    variants = douyin_video_variants(detail)
    return variants[0]["url"] if variants else None


def summarize_douyin_video_variants(detail: dict[str, Any], selected_url: str | None = None) -> dict[str, Any]:
    variants = douyin_video_variants(detail)
    selected = next((v for v in variants if v.get("url") == selected_url), variants[0] if variants else None)
    def compact(v: dict[str, Any] | None) -> dict[str, Any] | None:
        if not v:
            return None
        return {k: v.get(k) for k in ["source", "gear_name", "quality_type", "definition", "width", "height", "fps", "bit_rate", "is_h265", "is_hdr", "data_size"]}
    return {"variant_count": len(variants), "selected": compact(selected), "top_variants": [compact(v) for v in variants[:5]]}


def resolve_play_url_cdp(aweme_id: str) -> tuple[str, dict[str, Any]]:
    target = find_douyin_target()
    ws = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=30, suppress_origin=True)
    try:
        cdp_call(ws, "Runtime.enable", msg_id=1)
        cdp_call(ws, "Page.bringToFront", msg_id=2)
        res = cdp_call(
            ws,
            "Runtime.evaluate",
            {"expression": build_cdp_detail_expression(aweme_id), "awaitPromise": True, "returnByValue": True, "timeout": 60000},
            msg_id=3,
        )
    finally:
        ws.close()
    value = res.get("result", {}).get("value")
    if not value:
        raise RuntimeError(f"CDP detail fetch returned no value: {res}")
    if not value.get("ok"):
        raise RuntimeError(f"CDP detail fetch failed: HTTP {value.get('status')} {str(value.get('text'))[:200]}")
    detail = value.get("data")
    if not isinstance(detail, dict):
        raise RuntimeError(f"CDP detail fetch returned non-JSON body: {str(value.get('text'))[:200]}")
    play_url = pick_best_play_url(detail)
    if not play_url:
        raise RuntimeError("CDP detail JSON did not contain a playable URL")
    return play_url, detail


def get_candidate(aweme_id: str | None = None) -> dict | None:
    with connect() as conn:
        if aweme_id:
            row = conn.execute(
                "SELECT aweme_id, douyin_url FROM beauty.ai_beauty_candidates WHERE aweme_id=%s",
                (aweme_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT aweme_id, douyin_url
                FROM beauty.ai_beauty_candidates
                WHERE candidate_status IN ('batch_selected', 'failed') AND douyin_url IS NOT NULL
                ORDER BY priority_score DESC, discovered_at ASC
                LIMIT 1
                """
            ).fetchone()
    return {"aweme_id": row[0], "douyin_url": row[1]} if row else None


def mark_candidate(aweme_id: str, status: str, **fields) -> None:
    allowed = {"local_video_path", "analysis_dir", "duration_seconds", "width", "height", "last_error"}
    updates = ["candidate_status = %(status)s"]
    params = {"aweme_id": aweme_id, "status": status}
    for key, value in fields.items():
        if key in allowed:
            updates.append(f"{key} = %({key})s")
            params[key] = value
    with connect() as conn:
        conn.execute(
            f"UPDATE beauty.ai_beauty_candidates SET {', '.join(updates)} WHERE aweme_id = %(aweme_id)s",
            params,
        )
        conn.commit()


def build_ytdlp_args(
    url: str,
    output_path: Path,
    *,
    cookies_path: Path = COOKIE_PATH,
    cookies_exist: bool | None = None,
) -> list[str]:
    if cookies_exist is None:
        cookies_exist = cookies_path.exists()
    cmd = [
        "python",
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--force-overwrites",
        "-o",
        str(output_path),
    ]
    if cookies_exist:
        cmd.extend(["--cookies", str(cookies_path)])
    cmd.append(url)
    return cmd


def download_with_ytdlp(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_ytdlp_args(url, output_path)
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        tail = "\n".join((proc.stderr or proc.stdout or "").splitlines()[-12:])
        raise RuntimeError(f"yt-dlp failed with exit {proc.returncode}: {tail}")


def download_direct_url(url: str, output_path: Path, *, referer: str = "https://www.douyin.com/") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": DEFAULT_UA,
            "Referer": referer,
            "Accept": "video/webm,video/mp4,video/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp, output_path.open("wb") as fh:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    if output_path.stat().st_size < 1024:
        raise RuntimeError(f"downloaded file is too small: {output_path.stat().st_size} bytes")


def process_candidate(aweme_id: str | None = None) -> dict:
    candidate = get_candidate(aweme_id)
    if not candidate:
        raise SystemExit("No AI Beauty candidate found")
    aweme_id = candidate["aweme_id"]
    url = candidate["douyin_url"]
    video_path = DOWNLOAD_DIR / f"{aweme_id}.mp4"
    analysis_dir = ANALYSIS_DIR / aweme_id
    try:
        try:
            download_with_ytdlp(url, video_path)
            download_method = "yt-dlp"
        except Exception:
            play_url, _detail = resolve_play_url_cdp(aweme_id)
            download_direct_url(play_url, video_path, referer=url)
            download_method = "cdp-detail-play-url"
        probe = ffprobe_json(video_path)
        if not has_video_stream(probe):
            video_path.unlink(missing_ok=True)
            mark_candidate(aweme_id, "failed", last_error="downloaded file has no video stream")
            return {"aweme_id": aweme_id, "status": "failed", "error": "no video stream"}
        dur = duration_seconds(probe)
        dims = dimensions(probe)
        sheet = make_contact_sheet(video_path, analysis_dir)
        mark_candidate(
            aweme_id,
            "downloaded",
            local_video_path=str(video_path),
            analysis_dir=str(analysis_dir),
            duration_seconds=dur,
            width=dims[0] if dims else None,
            height=dims[1] if dims else None,
            last_error=None,
        )
        return {"aweme_id": aweme_id, "status": "downloaded", "video": str(video_path), "contact_sheet": str(sheet), "duration": dur, "dimensions": dims, "download_method": download_method}
    except Exception as exc:
        video_path.unlink(missing_ok=True)
        mark_candidate(aweme_id, "failed", last_error=str(exc))
        return {"aweme_id": aweme_id, "status": "failed", "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Download and verify one AI Beauty candidate with yt-dlp or CDP detail/play_addr fallback.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--aweme-id")
    group.add_argument("--next", action="store_true")
    args = parser.parse_args()
    result = process_candidate(args.aweme_id if args.aweme_id else None)
    print(result)
    return 0 if result.get("status") == "downloaded" else 1


if __name__ == "__main__":
    raise SystemExit(main())
