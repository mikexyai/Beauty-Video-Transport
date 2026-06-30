from __future__ import annotations

import argparse
import json

import sys
from pathlib import Path
from typing import Any

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import connect


def summarize_local_artifact_state(local_video_path: str | None, local_file_deleted: bool | None = None) -> dict[str, Any]:
    path = Path(local_video_path) if local_video_path else None
    exists = bool(path and path.exists())
    deleted = local_file_deleted is True
    if not path:
        role = "none"
    elif deleted and not exists:
        role = "historical_deleted"
    elif exists:
        role = "current_file"
    else:
        role = "missing_unconfirmed"
    return {
        "local_video_path": str(path) if path else None,
        "local_path_exists": exists,
        "local_file_deleted": deleted,
        "local_video_path_role": role,
    }


def counts_by_status() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT candidate_status, count(*)
            FROM beauty.ai_beauty_candidates
            GROUP BY candidate_status
            ORDER BY candidate_status
            """
        ).fetchall()
    return [{"status": r[0], "count": r[1]} for r in rows]


def latest_candidates(limit: int, status: str | None = None) -> list[dict]:
    params = {"limit": limit}
    where = ""
    if status:
        where = "WHERE c.candidate_status = %(status)s"
        params["status"] = status
    with connect() as conn:
        cur = conn.execute(
            f"""
            SELECT c.aweme_id, c.candidate_status, c.priority_score, c.douyin_url, c.local_video_path,
                   c.analysis_dir, c.last_error, c.discovered_at, u.local_file_deleted
            FROM beauty.ai_beauty_candidates c
            LEFT JOIN beauty.ai_beauty_uploads u ON u.aweme_id = c.aweme_id
            {where}
            ORDER BY c.discovered_at DESC, c.id DESC
            LIMIT %(limit)s
            """,
            params,
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    for row in rows:
        row.update(summarize_local_artifact_state(row.get("local_video_path"), row.get("local_file_deleted")))
    return rows


def latest_uploads(limit: int) -> list[dict]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT u.aweme_id, u.youtube_video_id, u.youtube_url, u.title, u.tags, u.uploaded_at,
                   u.local_file_deleted, c.local_video_path
            FROM beauty.ai_beauty_uploads u
            LEFT JOIN beauty.ai_beauty_candidates c ON c.aweme_id = u.aweme_id
            ORDER BY u.uploaded_at DESC, u.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    for row in rows:
        row.update(summarize_local_artifact_state(row.get("local_video_path"), row.get("local_file_deleted")))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only AI Beauty isolated table status report.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--status")
    parser.add_argument("--uploads", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = {"counts_by_status": counts_by_status()}
    if args.uploads:
        report["uploads"] = latest_uploads(args.limit)
    else:
        report["candidates"] = latest_candidates(args.limit, status=args.status)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
