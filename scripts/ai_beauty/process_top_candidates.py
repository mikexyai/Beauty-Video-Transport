from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.rank_candidates import rank_candidates
from scripts.ai_beauty.repositories.candidates import DEFAULT_CANDIDATE_REPOSITORY, CandidateRepository
from scripts.ai_beauty.state import BATCH_SELECTED_STATUS

DEFAULT_TOP_LIMIT = 3
DEFAULT_ARCHIVE_LIMIT = 1000


def _score_value(candidate: dict[str, Any]) -> float:
    value = candidate.get("priority_score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def select_top_candidates(candidates: Iterable[dict[str, Any]], *, limit: int = DEFAULT_TOP_LIMIT) -> list[dict[str, Any]]:
    """Return at most top-N candidates by priority_score without mutating input."""
    ranked = [dict(c) for c in candidates]
    ranked.sort(key=lambda c: (_score_value(c), str(c.get("aweme_id") or "")), reverse=True)
    for item in ranked[:limit]:
        item["candidate_status"] = BATCH_SELECTED_STATUS
    return ranked[:limit]


def archive_non_top_candidates(
    candidates: Iterable[dict[str, Any]],
    *,
    selected_aweme_ids: set[str],
    max_archive: int = DEFAULT_ARCHIVE_LIMIT,
) -> list[dict[str, Any]]:
    """Return non-selected candidates annotated for archive, capped by max_archive.

    The original score and metadata are preserved. Capping happens after sorting by
    score desc so the archive keeps the best candidates for future re-ranking.
    """
    archived: list[dict[str, Any]] = []
    for candidate in candidates:
        aweme_id = str(candidate.get("aweme_id") or "")
        if not aweme_id or aweme_id in selected_aweme_ids:
            continue
        item = dict(candidate)
        item["archive_reason"] = "not_top_3"
        archived.append(item)
    archived.sort(key=lambda c: (_score_value(c), str(c.get("aweme_id") or "")), reverse=True)
    return archived[:max_archive]


def fetch_pool(
    limit: int = DEFAULT_ARCHIVE_LIMIT + DEFAULT_TOP_LIMIT,
    *,
    repository: CandidateRepository = DEFAULT_CANDIDATE_REPOSITORY,
) -> list[dict[str, Any]]:
    return repository.fetch_active_pool(limit=limit)


def apply_batch_selection(
    ranked: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    archived: list[dict[str, Any]],
    *,
    archive_limit: int = DEFAULT_ARCHIVE_LIMIT,
    dry_run: bool = False,
    repository: CandidateRepository = DEFAULT_CANDIDATE_REPOSITORY,
) -> dict[str, Any]:
    selected_ids = [str(c["aweme_id"]) for c in selected]
    archived_ids = [str(c["aweme_id"]) for c in archived]
    ranked_by_id = {str(c["aweme_id"]): c for c in ranked}
    if dry_run:
        return {"updated_scores": 0, "selected": selected_ids, "archived": archived_ids, "pruned_archived": 0}

    repository.update_priority_scores(ranked)
    repository.mark_batch_selected(selected_ids)
    repository.mark_archived(archived_ids, "Archived: not in current top 3; kept for future re-ranking.")
    pruned = repository.prune_archive_overflow(archive_limit=archive_limit)
    return {
        "updated_scores": len(ranked_by_id),
        "selected": selected_ids,
        "archived": archived_ids,
        "pruned_archived": len(pruned),
    }


def prepare_top_batch(
    *,
    top_limit: int = DEFAULT_TOP_LIMIT,
    archive_limit: int = DEFAULT_ARCHIVE_LIMIT,
    dry_run: bool = False,
    repository: CandidateRepository = DEFAULT_CANDIDATE_REPOSITORY,
) -> dict[str, Any]:
    pool = fetch_pool(limit=archive_limit + top_limit, repository=repository)
    ranked = rank_candidates(pool)
    selected = select_top_candidates(ranked, limit=top_limit)
    selected_ids = {str(c["aweme_id"]) for c in selected}
    archived = archive_non_top_candidates(ranked, selected_aweme_ids=selected_ids, max_archive=archive_limit)
    applied = apply_batch_selection(ranked, selected, archived, archive_limit=archive_limit, dry_run=dry_run, repository=repository)
    return {
        "top_limit": top_limit,
        "archive_limit": archive_limit,
        "pool_count": len(pool),
        "selected": selected,
        "archived_count": len(archived),
        "archived_sample": archived[:10],
        "applied": applied,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an AI Beauty top-3 candidate batch: mark selected as batch_selected and archive the rest for future re-ranking.")
    parser.add_argument("--top-limit", type=int, default=DEFAULT_TOP_LIMIT)
    parser.add_argument("--archive-limit", type=int, default=DEFAULT_ARCHIVE_LIMIT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.top_limit < 1:
        raise SystemExit("--top-limit must be >= 1")
    if args.archive_limit < 1:
        raise SystemExit("--archive-limit must be >= 1")
    result = prepare_top_batch(top_limit=args.top_limit, archive_limit=args.archive_limit, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
