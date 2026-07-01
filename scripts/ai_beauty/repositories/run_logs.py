from __future__ import annotations

import json
from typing import Any, Callable, Iterable

from scripts.ai_beauty.db import connect


BLOCKING_STATUSES = {"download_failed", "upload_failed", "process_failed", "process_output_unparseable", "needs_screening"}
SKIPPED_DECISIONS = {"skipped", "review", "failed"}


def _count_items(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (list, tuple, set)):
        return len(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_nonzero_code(value: Any) -> bool:
    if value is None:
        return False
    parsed = _optional_int(value)
    return parsed != 0 if parsed is not None else True


def _is_zero_or_missing(value: Any) -> bool:
    if value is None:
        return True
    return _optional_int(value) == 0


def _failed_step(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "")
    if item.get("failed_step"):
        return str(item["failed_step"])
    if status == "download_failed":
        return "download_process"
    if status == "upload_failed" or _has_nonzero_code(item.get("upload_rc")) or _has_nonzero_code(item.get("dry_run_rc")):
        return "upload"
    if status in {"process_failed", "process_output_unparseable"}:
        return "process_selected"
    if status == "needs_screening":
        return "screening"
    return str(item.get("step") or "workflow")


def _returncode(item: dict[str, Any]) -> int | None:
    for key in ("returncode", "rc"):
        if item.get(key) is not None:
            return _optional_int(item[key])
    if item.get("status") == "upload_failed":
        if _has_nonzero_code(item.get("dry_run_rc")):
            return _optional_int(item["dry_run_rc"])
        if item.get("upload_rc") is not None:
            return _optional_int(item["upload_rc"])
    nested_download = item.get("download")
    if isinstance(nested_download, dict) and nested_download.get("returncode") is not None:
        return _optional_int(nested_download["returncode"])
    return None


def _blocker_text(item: dict[str, Any]) -> str | None:
    status = str(item.get("status") or "")
    aweme_id = item.get("aweme_id")
    if status == "needs_screening":
        return f"vision_required:{aweme_id}" if aweme_id else "vision_required"
    if status in BLOCKING_STATUSES and aweme_id and not item.get("reason"):
        return f"{status}:{aweme_id}" if aweme_id else status
    explicit = item.get("reason") or item.get("error") or item.get("blocker")
    if explicit:
        return str(explicit)
    if status in BLOCKING_STATUSES:
        return status
    return None


def build_run_summary(steps: Iterable[dict[str, Any]]) -> dict[str, Any]:
    step_list = [dict(step) for step in steps]
    counts: dict[str, Any] = {
        "collection": {"searches": 0, "found": 0, "upserted": 0, "errors": 0},
        "selection": {"selected": 0, "reselected": 0},
        "download_process": {"attempted": 0, "downloaded": 0, "download_failed": 0, "needs_screening": 0, "uploaded": 0, "upload_failed": 0},
        "screening": {"screened": 0, "approved": 0, "skipped": 0},
        "upload": {"attempted": 0, "dry_run_attempted": 0, "upload_attempted": 0, "uploaded": 0, "failed": 0},
        "verification": {"checked": 0, "ok": 0, "failed": 0},
        "cleanup": {"attempted": 0, "deleted": 0, "failed": 0},
        "blockers": 0,
    }
    normalized_steps: list[dict[str, Any]] = []
    blockers: list[str] = []
    retry_context: list[dict[str, Any]] = []
    seen_blockers: set[str] = set()

    def add_blocker(item: dict[str, Any]) -> None:
        blocker = _blocker_text(item)
        if not blocker or blocker == "None":
            return
        if blocker not in seen_blockers:
            seen_blockers.add(blocker)
            blockers.append(blocker)
        context = {
            "aweme_id": item.get("aweme_id"),
            "failed_step": _failed_step(item),
            "status": item.get("status"),
            "error": item.get("error"),
            "reason": item.get("reason") or item.get("blocker"),
            "command": item.get("command") or item.get("upload_command") or item.get("dry_run_command"),
            "returncode": _returncode(item),
        }
        context = {key: value for key, value in context.items() if value is not None}
        if context:
            retry_context.append(context)
        normalized_steps.append({"step": "blocker", **context, "blocker": blocker})

    def add_process_result(result: dict[str, Any]) -> None:
        status = str(result.get("status") or "")
        counts["download_process"]["attempted"] += 1
        if status in counts["download_process"]:
            counts["download_process"][status] += 1
        if isinstance(result.get("download"), dict) and result["download"].get("status") == "downloaded":
            counts["download_process"]["downloaded"] += 1
        normalized_steps.append({"step": "download_process", "aweme_id": result.get("aweme_id"), "status": status})

        decision = result.get("decision")
        if result.get("screening_id") is not None or decision is not None:
            counts["screening"]["screened"] += 1
            if decision == "approved":
                counts["screening"]["approved"] += 1
            if decision in SKIPPED_DECISIONS:
                counts["screening"]["skipped"] += 1
            normalized_steps.append({"step": "screening", "aweme_id": result.get("aweme_id"), "decision": decision, "status": status})

        if status in {"uploaded", "upload_failed"} or result.get("dry_run_rc") is not None or result.get("upload_rc") is not None:
            counts["upload"]["attempted"] += 1
            if result.get("dry_run_rc") is not None:
                counts["upload"]["dry_run_attempted"] += 1
            if result.get("upload_rc") is not None and _is_zero_or_missing(result.get("dry_run_rc")):
                counts["upload"]["upload_attempted"] += 1
            if status == "uploaded" or result.get("youtube_video_id") or result.get("uploaded"):
                counts["upload"]["uploaded"] += 1
            if status == "upload_failed" or _has_nonzero_code(result.get("dry_run_rc")) or _has_nonzero_code(result.get("upload_rc")):
                counts["upload"]["failed"] += 1
            normalized_steps.append({"step": "upload", "aweme_id": result.get("aweme_id"), "status": status, "dry_run_rc": result.get("dry_run_rc"), "upload_rc": result.get("upload_rc")})

        cleanup = result.get("cleanup")
        if isinstance(cleanup, dict):
            counts["cleanup"]["attempted"] += 1
            if cleanup.get("deleted"):
                counts["cleanup"]["deleted"] += 1
            else:
                counts["cleanup"]["failed"] += 1
            normalized_steps.append({"step": "cleanup", "aweme_id": result.get("aweme_id"), **cleanup})

        if status in BLOCKING_STATUSES or result.get("blocker"):
            add_blocker(result)

    for step in step_list:
        normalized_steps.append(step)
        step_name = step.get("step")
        if step_name in {"collect_select", "search"}:
            collection = step.get("collection") if isinstance(step.get("collection"), dict) else step
            searches = collection.get("searches") if isinstance(collection, dict) else None
            counts["collection"]["searches"] += _count_items(searches)
            counts["collection"]["found"] += _count_items(collection.get("total_found") if isinstance(collection, dict) else step.get("found"))
            counts["collection"]["upserted"] += _count_items(collection.get("total_upserted") if isinstance(collection, dict) else step.get("upserted"))
            counts["collection"]["errors"] += _count_items(collection.get("errors") if isinstance(collection, dict) else step.get("errors"))
            counts["selection"]["selected"] += _count_items(step.get("selected"))
        elif step_name == "reselect":
            counts["selection"]["reselected"] += _count_items(step.get("selected"))
        elif step_name == "process_iteration":
            for result in step.get("results") or []:
                if isinstance(result, dict):
                    add_process_result(result)
            for blocker in step.get("hard_blockers") or []:
                add_blocker({"step": "blocker", "blocker": blocker})
        elif step_name in {"screen", "screening"} or "decision" in step:
            counts["screening"]["screened"] += 1
            if step.get("decision") == "approved":
                counts["screening"]["approved"] += 1
            if step.get("decision") in SKIPPED_DECISIONS:
                counts["screening"]["skipped"] += 1
        elif step_name == "upload":
            counts["upload"]["attempted"] += 1
            if step.get("youtube_video_id") or step.get("uploaded"):
                counts["upload"]["uploaded"] += 1
            if step.get("status") == "upload_failed" or _has_nonzero_code(step.get("returncode")):
                counts["upload"]["failed"] += 1
        elif step_name == "verification":
            counts["verification"]["checked"] += _count_items(step.get("checked"))
            counts["verification"]["ok"] += _count_items(step.get("ok"))
            counts["verification"]["failed"] += _count_items(step.get("failed"))
        elif step_name == "cleanup":
            counts["cleanup"]["attempted"] += 1
            if step.get("deleted"):
                counts["cleanup"]["deleted"] += 1
            else:
                counts["cleanup"]["failed"] += 1
        if step_name == "blocker" or step.get("blocker") or step.get("status") in BLOCKING_STATUSES:
            add_blocker(step)

    counts["blockers"] = len(blockers)
    uploads = counts["upload"]["uploaded"]
    screened = counts["screening"]["screened"]
    skipped = counts["screening"]["skipped"]
    return {
        "step_count": len(step_list),
        "counts": counts,
        "uploads": uploads,
        "screened": screened,
        "skipped": skipped,
        "blockers": blockers,
        "retry_context": retry_context,
        "steps": step_list,
        "normalized_steps": normalized_steps,
    }


class RunLogRepository:
    def __init__(self, connect_fn: Callable[[], Any] | None = connect):
        self._connect = connect_fn or connect

    def start_run(self, run_id: str, *, job_type: str, status: str = "running", summary: dict[str, Any] | None = None) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO beauty.ai_beauty_run_logs (run_id, job_type, status, summary_json)
                VALUES (%(run_id)s, %(job_type)s, %(status)s, %(summary_json)s)
                ON CONFLICT (run_id) DO UPDATE SET
                    job_type = EXCLUDED.job_type,
                    status = EXCLUDED.status,
                    summary_json = EXCLUDED.summary_json
                RETURNING id
                """,
                {
                    "run_id": run_id,
                    "job_type": job_type,
                    "status": status,
                    "summary_json": json.dumps(summary or {}, ensure_ascii=False),
                },
            ).fetchone()
            conn.commit()
        return int(row[0])

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: dict[str, Any],
        candidates_found: int = 0,
        candidates_screened: int = 0,
        videos_uploaded: int = 0,
        videos_skipped: int = 0,
        error_message: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE beauty.ai_beauty_run_logs
                SET finished_at = now(),
                    status = %(status)s,
                    candidates_found = %(candidates_found)s,
                    candidates_screened = %(candidates_screened)s,
                    videos_uploaded = %(videos_uploaded)s,
                    videos_skipped = %(videos_skipped)s,
                    error_message = %(error_message)s,
                    summary_json = %(summary_json)s
                WHERE run_id = %(run_id)s
                """,
                {
                    "run_id": run_id,
                    "status": status,
                    "candidates_found": candidates_found,
                    "candidates_screened": candidates_screened,
                    "videos_uploaded": videos_uploaded,
                    "videos_skipped": videos_skipped,
                    "error_message": error_message,
                    "summary_json": json.dumps(summary, ensure_ascii=False),
                },
            )
            conn.commit()

    def record_completed_run(self, run_id: str, *, job_type: str, steps: list[dict[str, Any]], status: str = "ok") -> int:
        summary = build_run_summary(steps)
        run_pk = self.start_run(run_id, job_type=job_type, summary={"steps": []})
        self.finish_run(
            run_id,
            status=status,
            summary=summary,
            candidates_found=sum(int(s.get("found") or 0) for s in steps if s.get("step") == "search"),
            candidates_screened=summary["screened"],
            videos_uploaded=summary["uploads"],
            videos_skipped=summary["skipped"],
            error_message="; ".join(summary["blockers"]) or None,
        )
        return run_pk


DEFAULT_RUN_LOG_REPOSITORY = RunLogRepository()
