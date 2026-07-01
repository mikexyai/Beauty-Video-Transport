from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.repositories.run_logs import DEFAULT_RUN_LOG_REPOSITORY, build_run_summary
from scripts.ai_beauty.report_status import latest_uploads
from scripts.ai_beauty.scheduled_run import DEFAULT_KEYWORDS, run_scheduled_collection, parse_keywords
from scripts.ai_beauty.process_selected import fetch_batch_selected


def operator_should_continue(
    *,
    uploads_this_run: int,
    target_uploads: int,
    hard_blocker: str | None,
    active_candidates_available: bool,
    iteration: int = 0,
    max_iterations: int = 20,
) -> bool:
    if hard_blocker:
        return False
    if uploads_this_run >= target_uploads:
        return False
    if not active_candidates_available:
        return False
    if iteration >= max_iterations:
        return False
    return True


def summarize_operator_iteration(results: list[dict[str, Any]]) -> dict[str, Any]:
    uploaded = [r for r in results if r.get("status") == "uploaded"]
    screened_out = [r for r in results if r.get("candidate_status") == "screened_out" or r.get("status") == "screened_not_uploaded"]
    hard_blockers: list[str] = []
    for item in results:
        status = item.get("status")
        if status in {"download_failed", "upload_failed", "process_failed", "process_output_unparseable"}:
            suffix = f":{item.get('aweme_id')}" if item.get("aweme_id") else ""
            hard_blockers.append(f"{status}{suffix}")
        if status == "needs_screening":
            suffix = f":{item.get('aweme_id')}" if item.get("aweme_id") else ""
            hard_blockers.append(f"vision_required{suffix}")
    return {
        "uploaded": len(uploaded),
        "screened_out": len(screened_out),
        "hard_blockers": hard_blockers,
        "results": results,
    }


def count_uploads() -> int:
    return len(latest_uploads(10_000))


def build_process_selected_command(aweme_id: str, *, auto_upload: bool) -> list[str]:
    # Use module execution instead of a script path. Running
    # scripts/ai_beauty/process_selected.py directly puts scripts/ai_beauty on
    # sys.path, where operator.py shadows the stdlib operator module during
    # argparse -> re -> enum imports on Windows/Python 3.11.
    cmd = [sys.executable, "-m", "scripts.ai_beauty.process_selected", "--aweme-id", aweme_id]
    if auto_upload:
        cmd.append("--auto-upload")
    return cmd


def run_process_selected(aweme_id: str, *, auto_upload: bool) -> dict[str, Any]:
    cmd = build_process_selected_command(aweme_id, auto_upload=auto_upload)
    proc = subprocess.run(cmd, cwd=str(PROJECT_BOOTSTRAP_ROOT), text=True, capture_output=True)
    if proc.returncode != 0:
        return {
            "aweme_id": aweme_id,
            "status": "process_failed",
            "failed_step": "process_selected",
            "error": (proc.stderr or proc.stdout)[-2000:],
            "command": cmd,
            "returncode": proc.returncode,
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "aweme_id": aweme_id,
            "status": "process_output_unparseable",
            "failed_step": "process_selected",
            "error": "process_selected output was not valid JSON",
            "stdout": proc.stdout[-2000:],
            "command": cmd,
            "returncode": proc.returncode,
        }
    results = payload.get("results") or []
    return results[0] if results else {"aweme_id": aweme_id, "status": "no_result"}


def run_operator(
    *,
    target_uploads: int = 3,
    keywords: str = DEFAULT_KEYWORDS,
    pages: int = 1,
    count: int = 10,
    archive_limit: int = 1000,
    dry_run: bool = False,
    run_id: str | None = None,
    max_iterations: int = 20,
) -> dict[str, Any]:
    run_id = run_id or "ai-beauty-operator-manual"
    steps: list[dict[str, Any]] = []
    DEFAULT_RUN_LOG_REPOSITORY.start_run(run_id, job_type="ai_beauty_operator", summary={"steps": []})
    starting_upload_count = count_uploads()
    hard_blocker: str | None = None

    collection = run_scheduled_collection(
        keywords=parse_keywords(keywords),
        pages=pages,
        count=count,
        top_limit=target_uploads,
        archive_limit=archive_limit,
        dry_run=dry_run,
        run_id=run_id,
    )
    steps.append({"step": "collect_select", "collection": collection.get("collection"), "selected": [x.get("aweme_id") for x in collection.get("batch", {}).get("selected", [])]})

    # Deterministic operator can download/template selected candidates. Hermes cron
    # still supplies vision JSON before --auto-upload can approve and upload.
    iteration = 0
    while True:
        uploads_this_run = count_uploads() - starting_upload_count
        selected = fetch_batch_selected(limit=max(1, target_uploads - uploads_this_run))
        if not operator_should_continue(
            uploads_this_run=uploads_this_run,
            target_uploads=target_uploads,
            hard_blocker=hard_blocker,
            active_candidates_available=bool(selected),
            iteration=iteration,
            max_iterations=max_iterations,
        ):
            if iteration >= max_iterations and not hard_blocker and uploads_this_run < target_uploads:
                hard_blocker = "max_iterations_reached"
            break
        iteration += 1
        iteration_results = []
        for row in selected:
            if dry_run:
                result = {"aweme_id": row["aweme_id"], "status": "dry_run_selected"}
            else:
                result = run_process_selected(str(row["aweme_id"]), auto_upload=True)
            iteration_results.append(result)
        summary = summarize_operator_iteration(iteration_results)
        steps.append({"step": "process_iteration", **summary})
        if summary["hard_blockers"]:
            hard_blocker = "; ".join(summary["hard_blockers"])
        if summary["uploaded"] == 0:
            # Select next active candidates if current batch got screened_out or no-op.
            collection = run_scheduled_collection(
                keywords=parse_keywords(keywords),
                pages=pages,
                count=count,
                top_limit=max(1, target_uploads - uploads_this_run),
                archive_limit=archive_limit,
                skip_search=True,
                dry_run=dry_run,
                run_id=run_id,
            )
            steps.append({"step": "reselect", "selected": [x.get("aweme_id") for x in collection.get("batch", {}).get("selected", [])]})
            if not collection.get("batch", {}).get("selected"):
                hard_blocker = hard_blocker or "no_active_candidates"

    final_uploads = count_uploads() - starting_upload_count
    if hard_blocker:
        steps.append({"step": "blocker", "reason": hard_blocker, "blocker": hard_blocker})
    final_summary = build_run_summary(steps)
    final_status = "ok" if final_uploads >= target_uploads else "blocked" if hard_blocker else "partial"
    DEFAULT_RUN_LOG_REPOSITORY.finish_run(
        run_id,
        status=final_status,
        summary=final_summary,
        candidates_found=sum(int(s.get("collection", {}).get("total_found") or 0) for s in steps if isinstance(s.get("collection"), dict)),
        candidates_screened=final_summary["screened"],
        videos_uploaded=final_uploads,
        videos_skipped=final_summary["skipped"],
        error_message=hard_blocker,
    )
    return {
        "run_id": run_id,
        "status": final_status,
        "target_uploads": target_uploads,
        "uploads_this_run": final_uploads,
        "hard_blocker": hard_blocker,
        "summary": final_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Beauty deterministic operator: collect/select/process until target uploads or hard blocker.")
    parser.add_argument("--target-uploads", type=int, default=3)
    parser.add_argument("--keywords", default=DEFAULT_KEYWORDS)
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--archive-limit", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--max-iterations", type=int, default=20)
    args = parser.parse_args()
    result = run_operator(
        target_uploads=args.target_uploads,
        keywords=args.keywords,
        pages=args.pages,
        count=args.count,
        archive_limit=args.archive_limit,
        dry_run=args.dry_run,
        run_id=args.run_id,
        max_iterations=args.max_iterations,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] in {"ok", "partial", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
