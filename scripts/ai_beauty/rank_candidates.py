from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import connect

BEAUTY_KEYWORDS = {
    "美女": 14,
    "甜妹": 12,
    "氛围感": 10,
    "黑长直": 9,
    "清纯": 9,
    "美人": 9,
    "写真": 8,
    "高马尾": 7,
    "原相机": 6,
    "穿搭": 6,
    "国风": 6,
    "女神": 6,
    "肤白貌美": 6,
}
LOW_SIGNAL_KEYWORDS = {
    "翘臀": -10,
    "美臀": -10,
    "辣身材": -6,
    "凹凸有致": -4,
}
STAT_WEIGHTS = {
    "digg_count": 8.0,
    "share_count": 10.0,
    "collect_count": 9.0,
    "comment_count": 5.0,
    "download_count": 4.0,
}


def _number(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _stats(candidate: dict[str, Any]) -> dict[str, Any]:
    value = candidate.get("source_stats") or {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def _tags_text(candidate: dict[str, Any]) -> str:
    tags = candidate.get("hashtags") or []
    if isinstance(tags, str):
        tags = [tags]
    return " ".join(str(t) for t in tags if t)


def _orientation_score(candidate: dict[str, Any]) -> float:
    width = _number(candidate.get("width"))
    height = _number(candidate.get("height"))
    if not width or not height:
        return 0.0
    if height > width:
        ratio = height / width
        return 12.0 if ratio >= 1.45 else 8.0
    if width > height:
        return -4.0
    return 2.0


def _keyword_score(candidate: dict[str, Any]) -> float:
    text = f"{candidate.get('caption') or ''} {_tags_text(candidate)}"
    score = 0.0
    for keyword, weight in BEAUTY_KEYWORDS.items():
        if keyword in text:
            score += weight
    for keyword, weight in LOW_SIGNAL_KEYWORDS.items():
        if keyword in text:
            score += weight
    return score


def score_candidate(candidate: dict[str, Any]) -> float:
    """Score one Douyin AI Beauty candidate.

    Higher is better. The score intentionally combines public Douyin engagement,
    vertical Shorts-friendly format, and beauty-related textual signals. It is a
    ranking hint only; visual screening still makes the upload decision.
    """
    stats = _stats(candidate)
    score = 0.0
    for key, weight in STAT_WEIGHTS.items():
        score += math.log10(_number(stats.get(key)) + 1.0) * weight
    score += _orientation_score(candidate)
    score += _keyword_score(candidate)
    duration = _number(candidate.get("duration_seconds"))
    if duration:
        if 5 <= duration <= 60:
            score += 6.0
        elif duration > 180:
            score -= 8.0
    return round(score, 3)


def rank_candidates(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        item["priority_score"] = score_candidate(item)
        ranked.append(item)
    ranked.sort(key=lambda c: (c["priority_score"], str(c.get("aweme_id") or "")), reverse=True)
    return ranked


def fetch_candidates(status: str = "new", limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT aweme_id, caption, hashtags, width, height, duration_seconds, source_stats
            FROM beauty.ai_beauty_candidates
            WHERE candidate_status = %s
            ORDER BY discovered_at DESC, id DESC
            LIMIT %s
            """,
            (status, limit),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def update_priority_scores(ranked: Iterable[dict[str, Any]]) -> int:
    count = 0
    with connect() as conn:
        for candidate in ranked:
            conn.execute(
                """
                UPDATE beauty.ai_beauty_candidates
                SET priority_score = %s
                WHERE aweme_id = %s
                """,
                (candidate["priority_score"], candidate["aweme_id"]),
            )
            count += 1
        conn.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank isolated AI Beauty Douyin candidates by engagement and relevance.")
    parser.add_argument("--status", default="new")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ranked = rank_candidates(fetch_candidates(status=args.status, limit=args.limit))
    updated = 0 if args.dry_run else update_priority_scores(ranked)
    out = {
        "status": args.status,
        "limit": args.limit,
        "ranked": len(ranked),
        "updated": updated,
        "top": ranked[: min(10, len(ranked))],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
