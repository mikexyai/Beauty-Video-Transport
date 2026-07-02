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

from scripts.ai_beauty.db import connect
from scripts.ai_beauty.repositories.run_logs import DEFAULT_RUN_LOG_REPOSITORY, build_run_summary
from scripts.ai_beauty.report_status import latest_uploads
from scripts.ai_beauty.scheduled_run import DEFAULT_KEYWORDS, run_scheduled_collection, parse_keywords
from scripts.ai_beauty.process_selected import fetch_batch_selected
from scripts.ai_beauty.state import DOWNLOADED_STATUS, UPLOADED_STATUS


RECOVERY_ACTIONS = (
    "vision_required",
    "record_screening_needed",
    "upload_needed",
    "cleanup_needed",
)


def classify_recovery_candidate(row: dict[str, Any]) -> dict[str, Any]:
    status = str(row.get("candidate_status") or "")
    local_video_exists = bool(row.get("local_video_exists"))
    contact_sheet_exists = bool(row.get("contact_sheet_exists"))
    screening_json_exists = bool(row.get("screening_json_exists"))
    has_db_screening = bool(row.get("has_db_screening"))
    has_upload_row = bool(row.get("has_upload_row"))
    db_screening_decision = str(row.get("db_screening_decision") or "")
    local_file_deleted = row.get("local_file_deleted") is True
    action: str | None = None
    reason = "no_recovery_action"

    if status == DOWNLOADED_STATUS and local_video_exists and contact_sheet_exists and not screening_json_exists:
        action = "vision_required"
        reason = "downloaded video and contact sheet exist, but screening.json is missing"
    elif status == DOWNLOADED_STATUS and local_video_exists and screening_json_exists and not has_db_screening:
        action = "record_screening_needed"
        reason = "screening.json exists, but no DB screening row was recorded"
    elif status == DOWNLOADED_STATUS and has_db_screening and db_screening_decision == "approved" and not has_upload_row:
        action = "upload_needed"
        reason = "approved DB screening exists, but no upload row was recorded"
    elif status == UPLOADED_STATUS and has_upload_row and not local_file_deleted and local_video_exists:
        action = "cleanup_needed"
        reason = "upload row exists and local video still needs cleanup"

    return {**row, "action": action, "reason": reason}


def _artifact_state(row: dict[str, Any]) -> dict[str, Any]:
    local_video_path = row.get("local_video_path")
    analysis_dir = row.get("analysis_dir")
    video_path = Path(local_video_path) if local_video_path else None
    analysis_path = Path(analysis_dir) if analysis_dir else None
    contact_sheet_path = analysis_path / "contact_sheet.jpg" if analysis_path else None
    screening_json_path = analysis_path / "screening.json" if analysis_path else None
    return {
        "local_video_path": str(video_path) if video_path else None,
        "analysis_dir": str(analysis_path) if analysis_path else None,
        "contact_sheet_path": str(contact_sheet_path) if contact_sheet_path else None,
        "screening_json_path": str(screening_json_path) if screening_json_path else None,
        "local_video_exists": bool(video_path and video_path.exists()),
        "contact_sheet_exists": bool(contact_sheet_path and contact_sheet_path.exists()),
        "screening_json_exists": bool(screening_json_path and screening_json_path.exists()),
    }


def fetch_recovery_candidates(*, limit: int) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT c.aweme_id, c.candidate_status, c.local_video_path, c.analysis_dir,
                   EXISTS (
                       SELECT 1 FROM beauty.ai_beauty_screenings s
                       WHERE s.aweme_id = c.aweme_id
                   ) AS has_db_screening,
                   (
                       SELECT s.decision FROM beauty.ai_beauty_screenings s
                       WHERE s.aweme_id = c.aweme_id
                       ORDER BY s.id DESC
                       LIMIT 1
                   ) AS db_screening_decision,
                   EXISTS (
                       SELECT 1 FROM beauty.ai_beauty_uploads u
                       WHERE u.aweme_id = c.aweme_id
                   ) AS has_upload_row,
                   (
                       SELECT u.local_file_deleted FROM beauty.ai_beauty_uploads u
                       WHERE u.aweme_id = c.aweme_id
                       ORDER BY u.id DESC
                       LIMIT 1
                   ) AS local_file_deleted
            FROM beauty.ai_beauty_candidates c
            WHERE c.candidate_status IN (%s, %s)
            ORDER BY c.discovered_at DESC, c.id DESC
            LIMIT %s
            """,
            (DOWNLOADED_STATUS, UPLOADED_STATUS, limit),
        )
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    return [{**row, **_artifact_state(row)} for row in rows]


def build_recovery_plan(*, limit: int) -> dict[str, Any]:
    classified = [classify_recovery_candidate(row) for row in fetch_recovery_candidates(limit=limit)]
    actions = [row for row in classified if row.get("action")]
    counts = {action: 0 for action in RECOVERY_ACTIONS}
    for row in actions:
        counts[str(row["action"])] += 1
    return {
        "mode": "dry_run_plan",
        "counts": counts,
        "actions": actions,
        "informational": [row for row in classified if not row.get("action")],
    }


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
    dry_run_selected = [r for r in results if r.get("status") == "dry_run_selected"]
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
        "dry_run_selected": len(dry_run_selected),
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
    recover_pending: bool = False,
) -> dict[str, Any]:
    run_id = run_id or "ai-beauty-operator-manual"
    steps: list[dict[str, Any]] = []
    if recover_pending:
        if not dry_run:
            recovery_step = {
                "step": "recovery",
                "status": "unsupported",
                "blocker": "recover_pending_mutation_not_implemented",
            }
            summary = build_run_summary([recovery_step])
            return {
                "run_id": run_id,
                "status": "blocked",
                "target_uploads": target_uploads,
                "uploads_this_run": 0,
                "hard_blocker": "recover_pending_mutation_not_implemented",
                "summary": summary,
            }
        recovery = build_recovery_plan(limit=max(1, target_uploads))
        recovery_step = {"step": "recovery", **recovery}
        summary = build_run_summary([recovery_step])
        summary["steps"] = [recovery_step]
        summary["recovery"] = recovery
        return {
            "run_id": run_id,
            "status": "blocked",
            "target_uploads": target_uploads,
            "uploads_this_run": 0,
            "hard_blocker": "dry_run_recovery_plan",
            "summary": summary,
        }
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
        if dry_run and summary["dry_run_selected"]:
            summary["pending_candidates"] = [
                {"aweme_id": row.get("aweme_id"), "candidate_status": row.get("candidate_status") or row.get("status")}
                for row in selected
            ]
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
                if dry_run and summary["dry_run_selected"]:
                    hard_blocker = hard_blocker or "dry_run_no_progress"
                else:
                    hard_blocker = hard_blocker or "no_active_candidates"

    final_uploads = count_uploads() - starting_upload_count
    if hard_blocker:
        steps.append({"step": "blocker", "reason": hard_blocker, "blocker": hard_blocker})
    final_summary = build_run_summary(steps)
    final_summary["counts"]["dry_run_selected"] = sum(int(s.get("dry_run_selected") or 0) for s in steps)
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
    parser.add_argument("--recover-pending", action="store_true", help="Plan recovery actions for pending AI Beauty candidates. Mutating recovery is not implemented yet.")
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
        recover_pending=args.recover_pending,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result["status"] in {"ok", "partial", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
