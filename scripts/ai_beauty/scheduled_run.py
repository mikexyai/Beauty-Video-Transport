from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.process_top_candidates import prepare_top_batch
from scripts.ai_beauty.search_douyin import search_douyin, upsert_search_candidates

DEFAULT_KEYWORDS = "美女,甜妹,氛围感美女"


def parse_keywords(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_search_plan(keywords: list[str], *, pages: int, count: int) -> list[dict[str, int | str]]:
    if pages < 1:
        raise ValueError("pages must be >= 1")
    if count < 1:
        raise ValueError("count must be >= 1")
    plan: list[dict[str, int | str]] = []
    for keyword in keywords:
        for page in range(pages):
            plan.append({"keyword": keyword, "offset": page * count, "count": count})
    return plan


def collect_search_candidates(
    plan: list[dict[str, int | str]],
    *,
    dry_run: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    searches: list[dict[str, Any]] = []
    total_found = 0
    total_upserted = 0
    errors: list[dict[str, Any]] = []
    for step in plan:
        keyword = str(step["keyword"])
        offset = int(step["offset"])
        count = int(step["count"])
        try:
            result = search_douyin(keyword, offset=offset, count=count)
            candidates = result["candidates"]
            upserted = 0 if dry_run else upsert_search_candidates(
                candidates,
                keyword=keyword,
                run_id=run_id or f"scheduled:{keyword}:{offset}",
            )
            total_found += len(candidates)
            total_upserted += upserted
            searches.append({
                "keyword": keyword,
                "offset": offset,
                "count": count,
                "found": len(candidates),
                "upserted": upserted,
                "has_more": result.get("has_more"),
                "cursor": result.get("cursor"),
                "response_bytes": result.get("response_bytes"),
                "sample_aweme_ids": [c.get("aweme_id") for c in candidates[:5]],
            })
        except Exception as exc:
            errors.append({"keyword": keyword, "offset": offset, "count": count, "error": str(exc)})
    return {
        "searches": searches,
        "errors": errors,
        "total_found": total_found,
        "total_upserted": total_upserted,
    }


def run_scheduled_collection(
    *,
    keywords: list[str],
    pages: int,
    count: int,
    top_limit: int,
    archive_limit: int,
    skip_search: bool = False,
    dry_run: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    plan = build_search_plan(keywords, pages=pages, count=count)
    collection = {"searches": [], "errors": [], "total_found": 0, "total_upserted": 0, "skipped": True}
    if not skip_search:
        collection = collect_search_candidates(plan, dry_run=dry_run, run_id=run_id)
        collection["skipped"] = False
    batch = prepare_top_batch(top_limit=top_limit, archive_limit=archive_limit, dry_run=dry_run)
    return {
        "run_id": run_id,
        "dry_run": dry_run,
        "keywords": keywords,
        "search_plan": plan,
        "collection": collection,
        "batch": batch,
        "next_step": "Process only candidates whose candidate_status is batch_selected. If no batch_selected rows exist, wait for next scheduled search.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Beauty scheduled collection entrypoint: search, re-rank archived+new candidates, and select top 3.")
    parser.add_argument("--keywords", default=DEFAULT_KEYWORDS, help="Comma-separated Douyin search keywords")
    parser.add_argument("--pages", type=int, default=1, help="Search pages per keyword")
    parser.add_argument("--count", type=int, default=10, help="Results per search page")
    parser.add_argument("--top-limit", type=int, default=3)
    parser.add_argument("--archive-limit", type=int, default=1000)
    parser.add_argument("--skip-search", action="store_true", help="Only rerank existing new+archived candidates")
    parser.add_argument("--dry-run", action="store_true", help="Do not write search upserts or batch status changes")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    keywords = parse_keywords(args.keywords)
    if not keywords:
        raise SystemExit("No keywords provided")
    result = run_scheduled_collection(
        keywords=keywords,
        pages=args.pages,
        count=args.count,
        top_limit=args.top_limit,
        archive_limit=args.archive_limit,
        skip_search=args.skip_search,
        dry_run=args.dry_run,
        run_id=args.run_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if not result["collection"].get("errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
