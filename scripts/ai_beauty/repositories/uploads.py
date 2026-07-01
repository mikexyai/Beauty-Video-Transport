from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from scripts.ai_beauty.db import connect
from scripts.ai_beauty.state import APPROVED_STATUS, UPLOADED_STATUS


class UploadRepository:
    def __init__(self, connect_fn: Callable[[], Any] | None = connect) -> None:
        self.connect_fn = connect_fn

    def latest_approved(self, aweme_id: str) -> dict[str, Any]:
        if self.connect_fn is None:
            raise RuntimeError("UploadRepository requires a connect_fn for database operations")
        with self.connect_fn() as conn:
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

    def next_approved_aweme_id(self) -> str | None:
        if self.connect_fn is None:
            raise RuntimeError("UploadRepository requires a connect_fn for database operations")
        with self.connect_fn() as conn:
            row = conn.execute(
                """
                SELECT c.aweme_id
                FROM beauty.ai_beauty_candidates c
                JOIN beauty.ai_beauty_screenings s ON s.aweme_id = c.aweme_id
                LEFT JOIN beauty.ai_beauty_uploads u ON u.aweme_id = c.aweme_id
                WHERE c.candidate_status = %s AND s.decision = 'approved' AND u.id IS NULL
                ORDER BY c.priority_score DESC, c.discovered_at ASC, s.screened_at DESC
                LIMIT 1
                """,
                (APPROVED_STATUS,),
            ).fetchone()
        return row[0] if row else None

    def record_upload(self, info: dict[str, Any], upload_result: dict[str, Any]) -> None:
        if self.connect_fn is None:
            raise RuntimeError("UploadRepository requires a connect_fn for database operations")
        video_id = upload_result.get("video_id") or upload_result.get("id")
        if not video_id:
            raise ValueError("upload result did not include video_id")
        youtube_url = upload_result.get("url") or f"https://www.youtube.com/watch?v={video_id}"
        with self.connect_fn() as conn:
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
            conn.execute("UPDATE beauty.ai_beauty_candidates SET candidate_status=%s WHERE aweme_id=%s", (UPLOADED_STATUS, info["aweme_id"]))
            conn.commit()

    def fetch_candidate_local_video_path(self, aweme_id: str) -> str | None:
        if self.connect_fn is None:
            raise RuntimeError("UploadRepository requires a connect_fn for database operations")
        with self.connect_fn() as conn:
            row = conn.execute(
                "SELECT local_video_path FROM beauty.ai_beauty_candidates WHERE aweme_id=%s",
                (aweme_id,),
            ).fetchone()
        return str(row[0]) if row and row[0] else None

    def mark_local_file_deleted(self, aweme_id: str, deleted: bool) -> None:
        if self.connect_fn is None:
            raise RuntimeError("UploadRepository requires a connect_fn for database operations")
        with self.connect_fn() as conn:
            conn.execute("UPDATE beauty.ai_beauty_uploads SET local_file_deleted=%s WHERE aweme_id=%s", (deleted, aweme_id))
            conn.commit()


upload_repository = UploadRepository()
