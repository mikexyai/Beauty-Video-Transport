from __future__ import annotations

import argparse
import json
import sys
from typing import Any

PROJECT_BOOTSTRAP_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import connect
from scripts.ai_beauty.report_status import summarize_local_artifact_state

EXPECTED_CHANNEL_ID = "UCEPE24TT9ZpGpVs0vv3i7mw"
EXPECTED_CHANNEL_TITLE = "AI Beauty"


def summarize_video_status(item: dict[str, Any], *, delayed: bool = False) -> dict[str, Any]:
    snippet = item.get("snippet") or {}
    status = item.get("status") or {}
    processing = item.get("processingDetails") or {}
    content = item.get("contentDetails") or {}
    tags = snippet.get("tags") or []
    region_restriction = content.get("regionRestriction") or {}
    problems: list[str] = []
    if snippet.get("channelId") != EXPECTED_CHANNEL_ID:
        problems.append("wrong_channel")
    if status.get("privacyStatus") != "public":
        problems.append("not_public")
    if status.get("uploadStatus") not in {"processed", "uploaded"}:
        problems.append("bad_upload_status")
    processing_status = processing.get("processingStatus")
    if delayed:
        if processing_status != "succeeded":
            problems.append("processing_not_succeeded")
    elif processing_status not in {"succeeded", "processing", None}:
        problems.append("bad_processing_status")
    if snippet.get("description", "") != "":
        problems.append("non_empty_description")
    if len(tags) > 5:
        problems.append("too_many_tags")
    if region_restriction.get("blocked"):
        problems.append("region_restriction")
    return {
        "video_id": item.get("id"),
        "title": snippet.get("title"),
        "channel_id": snippet.get("channelId"),
        "channel_title": snippet.get("channelTitle"),
        "privacy_status": status.get("privacyStatus"),
        "upload_status": status.get("uploadStatus"),
        "processing_status": processing_status,
        "duration": content.get("duration"),
        "definition": content.get("definition"),
        "tag_count": len(tags),
        "description_empty": snippet.get("description", "") == "",
        "region_restriction": region_restriction,
        "ok": not problems,
        "problems": problems,
    }


def fetch_recent_upload_records(limit: int) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT u.aweme_id, u.youtube_video_id, u.youtube_url, u.title,
                   u.local_file_deleted, c.local_video_path
            FROM beauty.ai_beauty_uploads u
            LEFT JOIN beauty.ai_beauty_candidates c ON c.aweme_id = u.aweme_id
            ORDER BY u.uploaded_at DESC, u.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def attach_local_cleanup_context(check: dict[str, Any], rec: dict[str, Any]) -> None:
    check["aweme_id"] = rec.get("aweme_id")
    check["youtube_url"] = rec.get("youtube_url")
    check.update(summarize_local_artifact_state(rec.get("local_video_path"), rec.get("local_file_deleted")))
    if rec.get("local_file_deleted") is not True:
        check.setdefault("problems", []).append("local_file_not_deleted")
        check["ok"] = False


def verify_video_ids(video_ids: list[str], *, delayed: bool = False) -> list[dict[str, Any]]:
    if not video_ids:
        return []
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT / "youtube-upload"))
    import youtube_upload  # type: ignore

    youtube = youtube_upload.build_youtube("default")
    out: list[dict[str, Any]] = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="id,snippet,status,processingDetails,contentDetails",
            id=",".join(chunk),
        ).execute()
        found = {item.get("id"): item for item in resp.get("items", [])}
        for vid in chunk:
            item = found.get(vid)
            if item:
                out.append(summarize_video_status(item, delayed=delayed))
            else:
                out.append({"video_id": vid, "ok": False, "problems": ["not_found"]})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify recent AI Beauty YouTube uploads via Data API.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--delayed", action="store_true", help="Require final processing success; suitable for delayed post-upload checks")
    args = parser.parse_args()
    records = fetch_recent_upload_records(args.limit)
    by_id = {r["youtube_video_id"]: r for r in records}
    checks = verify_video_ids([r["youtube_video_id"] for r in records if r.get("youtube_video_id")], delayed=args.delayed)
    for check in checks:
        rec = by_id.get(check.get("video_id"), {})
        attach_local_cleanup_context(check, rec)
    report = {"count": len(checks), "ok_count": sum(1 for c in checks if c.get("ok")), "checks": checks}
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0 if all(c.get("ok") for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
