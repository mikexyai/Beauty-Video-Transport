from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "youtube-upload"))
sys.path.insert(0, str(ROOT / "scripts"))

from googleapiclient.errors import HttpError  # type: ignore
from youtube_upload import build_youtube  # type: ignore


def parse_recorded_at(value: str) -> datetime | None:
    if not value:
        return None
    s = value.strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        # PostgreSQL JSON default string: 2026-06-28 12:23:27+00:00
        return datetime.fromisoformat(s.replace(" ", "T", 1))
    except ValueError:
        return None


def parse_iso8601_duration_seconds(value: str) -> float | None:
    if not value:
        return None
    m = re.fullmatch(r"P(?:(?P<days>\d+(?:\.\d+)?)D)?(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?", value)
    if not m:
        return None
    days = float(m.group("days") or 0)
    hours = float(m.group("hours") or 0)
    minutes = float(m.group("minutes") or 0)
    seconds = float(m.group("seconds") or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    p = argparse.ArgumentParser(description="Check recent uploaded YouTube video API status grouped by token profile.")
    p.add_argument("--csv", default=str(ROOT / "upload_records.csv"))
    p.add_argument("--since-local", help="Local +08 timestamp inclusive, e.g. 2026-06-28T19:00:00+08:00")
    p.add_argument("--ids", help="Comma-separated YouTube IDs to check; if omitted, select by --since-local")
    p.add_argument("--parts", default="id,snippet,status,processingDetails,contentDetails,statistics")
    args = p.parse_args()

    rows = load_csv(Path(args.csv))
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        candidates = [r for r in rows if r.get("youtube_video_id") in wanted]
    else:
        if not args.since_local:
            raise SystemExit("Provide --since-local or --ids")
        since = parse_recorded_at(args.since_local)
        if since is None:
            raise SystemExit(f"Invalid --since-local: {args.since_local}")
        candidates = []
        for r in rows:
            dt = parse_recorded_at(r.get("recorded_at", ""))
            if dt and dt >= since and r.get("youtube_video_id"):
                candidates.append(r)

    by_profile: dict[str, list[dict]] = defaultdict(list)
    for r in candidates:
        by_profile[r.get("youtube_profile") or "default"].append(r)

    results = []
    errors = []
    for profile, prs in sorted(by_profile.items()):
        youtube = build_youtube(profile)
        ids = [r["youtube_video_id"] for r in prs]
        for i in range(0, len(ids), 50):
            chunk = ids[i:i+50]
            try:
                resp = youtube.videos().list(part=args.parts, id=",".join(chunk), maxResults=50).execute()
            except HttpError as e:
                payload = getattr(e, "content", b"").decode("utf-8", "ignore")
                errors.append({"profile": profile, "ids": chunk, "error": "HttpError", "status": getattr(e.resp, "status", None), "content": payload})
                continue
            items = {item.get("id"): item for item in resp.get("items", [])}
            for r in prs[i:i+50]:
                vid = r["youtube_video_id"]
                item = items.get(vid)
                if not item:
                    results.append({"profile": profile, "video_id": vid, "row": r, "exists": False})
                    continue
                content = item.get("contentDetails", {})
                status = item.get("status", {})
                proc = item.get("processingDetails", {})
                duration = content.get("duration")
                blocked = (content.get("regionRestriction") or {}).get("blocked") or []
                allowed = (content.get("regionRestriction") or {}).get("allowed") or []
                problem_signals = {
                    "uploadStatus": status.get("uploadStatus"),
                    "privacyStatus": status.get("privacyStatus"),
                    "failureReason": status.get("failureReason"),
                    "rejectionReason": status.get("rejectionReason"),
                    "processingStatus": proc.get("processingStatus"),
                    "processingFailureReason": proc.get("processingFailureReason"),
                    "duration": duration,
                    "duration_seconds": parse_iso8601_duration_seconds(duration or ""),
                    "blocked_count": len(blocked),
                    "allowed_count": len(allowed),
                    "blocked_sample": blocked[:20],
                    "allowed_sample": allowed[:20],
                    "embeddable": status.get("embeddable"),
                    "license": status.get("license"),
                    "publicStatsViewable": status.get("publicStatsViewable"),
                    "madeForKids": status.get("madeForKids"),
                    "viewCount": (item.get("statistics") or {}).get("viewCount"),
                }
                known_autofix_candidate = (
                    status.get("uploadStatus") == "processed"
                    and status.get("privacyStatus") == "public"
                    and not status.get("failureReason")
                    and not status.get("rejectionReason")
                    and not proc.get("processingFailureReason")
                    and (parse_iso8601_duration_seconds(duration or "") or 0) > 60
                    and len(blocked) >= 100
                )
                results.append({
                    "profile": profile,
                    "video_id": vid,
                    "exists": True,
                    "source_platform": r.get("source_platform"),
                    "source_id": r.get("bvid"),
                    "source_title": r.get("source_title"),
                    "youtube_title_csv": r.get("youtube_title"),
                    "youtube_title_api": (item.get("snippet") or {}).get("title"),
                    "youtube_url": r.get("youtube_url") or f"https://www.youtube.com/watch?v={vid}",
                    "signals": problem_signals,
                    "has_region_block": bool(blocked),
                    "known_autofix_candidate": known_autofix_candidate,
                    "raw_item": item,
                })

    print(json.dumps({"candidate_count": len(candidates), "results": results, "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
