from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import sys

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import PROJECT_ROOT, connect

YOUTUBE_UPLOAD = PROJECT_ROOT / "youtube-upload" / "youtube_upload.py"


def build_upload_args(*, file_path: str, title: str, tags: list[str], mode: str = "dry-run") -> list[str]:
    if len(tags) > 5:
        raise ValueError("AI Beauty uploads allow at most 5 tags")
    if mode not in {"dry-run", "upload"}:
        raise ValueError("mode must be dry-run or upload")
    return [
        "python",
        str(YOUTUBE_UPLOAD),
        mode,
        "--profile",
        "default",
        "--file",
        file_path,
        "--title",
        title,
        "--description",
        "",
        "--tags",
        ",".join(tags),
        "--privacyStatus",
        "public",
    ]


def latest_approved(aweme_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT c.aweme_id, c.local_video_path, s.id AS screening_id, s.recommended_title,
                   s.recommended_tags, s.selection_reason
            FROM beauty.ai_beauty_candidates c
            JOIN beauty.ai_beauty_screenings s ON s.aweme_id = c.aweme_id
            WHERE c.aweme_id = %s AND s.decision = 'approved'
            ORDER BY s.screened_at DESC, s.id DESC
            LIMIT 1
            """,
            (aweme_id,),
        ).fetchone()
    if not row:
        raise SystemExit(f"No approved AI Beauty screening found for aweme_id {aweme_id}")
    return {
        "aweme_id": row[0],
        "local_video_path": row[1],
        "screening_id": row[2],
        "title": row[3],
        "tags": list(row[4] or []),
        "selection_reason": row[5],
    }


def next_approved_aweme_id() -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT c.aweme_id
            FROM beauty.ai_beauty_candidates c
            JOIN beauty.ai_beauty_screenings s ON s.aweme_id = c.aweme_id
            LEFT JOIN beauty.ai_beauty_uploads u ON u.aweme_id = c.aweme_id
            WHERE c.candidate_status = 'approved' AND s.decision = 'approved' AND u.id IS NULL
            ORDER BY c.priority_score DESC, c.discovered_at ASC, s.screened_at DESC
            LIMIT 1
            """
        ).fetchone()
    return row[0] if row else None


def parse_upload_json(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    last: dict[str, Any] | None = None
    for idx, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(stdout[idx:])
        except json.JSONDecodeError:
            continue
        # Only accept objects that consume the rest of this slice except whitespace.
        # This ignores nested braces inside a larger pretty-printed object while
        # still handling progress-line JSON followed by a final upload JSON.
        if isinstance(value, dict) and not stdout[idx + end :].strip():
            last = value
    if last is None:
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                last = value
    if last is None:
        raise ValueError("Could not find JSON object in uploader output")
    return last


def record_upload(info: dict[str, Any], upload_result: dict[str, Any]) -> None:
    video_id = upload_result.get("video_id") or upload_result.get("id")
    if not video_id:
        raise ValueError("upload result did not include video_id")
    youtube_url = upload_result.get("url") or f"https://www.youtube.com/watch?v={video_id}"
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO beauty.ai_beauty_uploads (
                aweme_id, youtube_video_id, youtube_url, youtube_profile, title, description,
                tags, privacy_status, upload_status, upload_response_json, screening_id,
                selection_reason, local_file_deleted
            ) VALUES (%s, %s, %s, 'default', %s, '', %s, 'public', 'uploaded', %s, %s, %s, %s)
            ON CONFLICT (aweme_id) DO UPDATE SET
                youtube_video_id = EXCLUDED.youtube_video_id,
                youtube_url = EXCLUDED.youtube_url,
                title = EXCLUDED.title,
                tags = EXCLUDED.tags,
                upload_status = EXCLUDED.upload_status,
                upload_response_json = EXCLUDED.upload_response_json,
                screening_id = EXCLUDED.screening_id,
                selection_reason = EXCLUDED.selection_reason,
                local_file_deleted = EXCLUDED.local_file_deleted
            """,
            (
                info["aweme_id"],
                video_id,
                youtube_url,
                info["title"],
                info["tags"],
                json.dumps(upload_result, ensure_ascii=False),
                info["screening_id"],
                info.get("selection_reason"),
                False,
            ),
        )
        conn.execute("UPDATE beauty.ai_beauty_candidates SET candidate_status='uploaded' WHERE aweme_id=%s", (info["aweme_id"],))
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload approved AI Beauty candidates to YouTube default profile only.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--aweme-id")
    group.add_argument("--next-approved", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--upload", action="store_true")
    args = parser.parse_args()

    aweme_id = args.aweme_id or next_approved_aweme_id()
    if not aweme_id:
        raise SystemExit("No approved AI Beauty candidate found")
    info = latest_approved(aweme_id)
    file_path = info["local_video_path"]
    if not file_path or not Path(file_path).exists():
        raise SystemExit(f"Local video file missing for {aweme_id}: {file_path}")
    cmd = build_upload_args(file_path=file_path, title=info["title"], tags=info["tags"], mode="upload" if args.upload else "dry-run")
    proc = subprocess.run(cmd, cwd=str(YOUTUBE_UPLOAD.parent), text=True, capture_output=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        return proc.returncode
    result = parse_upload_json(proc.stdout)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "aweme_id": aweme_id, "result": result}, ensure_ascii=False, indent=2))
        return 0
    record_upload(info, result)
    print(json.dumps({"uploaded": True, "aweme_id": aweme_id, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
