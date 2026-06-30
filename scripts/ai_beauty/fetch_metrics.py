from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import connect


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_video_metric_item(item: dict[str, Any]) -> dict[str, Any]:
    stats = item.get("statistics") or {}
    content = item.get("contentDetails") or {}
    return {
        "youtube_video_id": item.get("id"),
        "views": _int_or_none(stats.get("viewCount")),
        "likes": _int_or_none(stats.get("likeCount")),
        "comments": _int_or_none(stats.get("commentCount")),
        "duration": content.get("duration"),
        "raw_metrics_json": item,
    }


def build_metric_upsert_params(metric: dict[str, Any], *, metric_date: str | date | None = None) -> dict[str, Any]:
    return {
        "youtube_video_id": metric["youtube_video_id"],
        "metric_date": str(metric_date or date.today()),
        "views": metric.get("views"),
        "likes": metric.get("likes"),
        "comments": metric.get("comments"),
        "raw_metrics_json": json.dumps(metric.get("raw_metrics_json") or metric, ensure_ascii=False),
    }


def fetch_ai_beauty_video_ids(limit: int) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT youtube_video_id
            FROM beauty.ai_beauty_uploads
            ORDER BY uploaded_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [str(r[0]) for r in rows if r[0]]


def fetch_youtube_public_metrics(video_ids: list[str]) -> list[dict[str, Any]]:
    if not video_ids:
        return []
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT / "youtube-upload"))
    import youtube_upload  # type: ignore

    youtube = youtube_upload.build_youtube("default")
    metrics: list[dict[str, Any]] = []
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="id,statistics,contentDetails,snippet,status",
            id=",".join(chunk),
        ).execute()
        for item in resp.get("items", []):
            metrics.append(parse_video_metric_item(item))
    return metrics


def upsert_metrics(metrics: list[dict[str, Any]], *, metric_date: str | date | None = None) -> int:
    count = 0
    with connect() as conn:
        for metric in metrics:
            params = build_metric_upsert_params(metric, metric_date=metric_date)
            conn.execute(
                """
                INSERT INTO beauty.ai_beauty_video_metrics (
                    youtube_video_id, metric_date, views, likes, comments, raw_metrics_json
                ) VALUES (
                    %(youtube_video_id)s, %(metric_date)s, %(views)s, %(likes)s, %(comments)s, %(raw_metrics_json)s
                )
                ON CONFLICT (youtube_video_id, metric_date) DO UPDATE SET
                    views = EXCLUDED.views,
                    likes = EXCLUDED.likes,
                    comments = EXCLUDED.comments,
                    raw_metrics_json = EXCLUDED.raw_metrics_json
                """,
                params,
            )
            count += 1
        conn.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch public YouTube metrics for AI Beauty uploads and store snapshots.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--metric-date")
    args = parser.parse_args()
    video_ids = fetch_ai_beauty_video_ids(args.limit)
    metrics = fetch_youtube_public_metrics(video_ids)
    written = 0 if args.dry_run else upsert_metrics(metrics, metric_date=args.metric_date)
    print(json.dumps({"video_count": len(video_ids), "metric_count": len(metrics), "written": written, "metrics": metrics}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
