from __future__ import annotations

import json
from typing import Any, Callable, Iterable

from scripts.ai_beauty.db import connect


def build_run_summary(steps: Iterable[dict[str, Any]]) -> dict[str, Any]:
    step_list = [dict(step) for step in steps]
    uploads = [s for s in step_list if s.get("step") == "upload" and (s.get("youtube_video_id") or s.get("uploaded"))]
    screened = [s for s in step_list if s.get("step") == "screen" or "decision" in s]
    skipped = [s for s in screened if s.get("decision") in {"skipped", "review", "failed"}]
    blockers = [str(s.get("reason") or s.get("error") or s.get("blocker")) for s in step_list if s.get("step") == "blocker" or s.get("blocker")]
    return {
        "step_count": len(step_list),
        "uploads": len(uploads),
        "screened": len(screened),
        "skipped": len(skipped),
        "blockers": [b for b in blockers if b and b != "None"],
        "steps": step_list,
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
