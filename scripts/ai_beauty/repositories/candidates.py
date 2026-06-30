from __future__ import annotations

import json
from typing import Any, Callable, Iterable

from scripts.ai_beauty.db import connect
from scripts.ai_beauty.state import (
    ACTIVE_STATUSES,
    ARCHIVE_PRUNED_STATUS,
    ARCHIVED_STATUS,
    BATCH_SELECTED_STATUS,
    SCREENED_OUT_STATUS,
    TERMINAL_STATUSES,
    UPLOADED_STATUS,
    assert_known_status,
)


class CandidateRepository:
    def __init__(self, connect_fn: Callable[[], Any] | None = connect):
        self._connect = connect_fn or connect

    @staticmethod
    def filter_storeable_candidates(
        candidates: Iterable[dict[str, Any]],
        *,
        excluded_aweme_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        excluded = excluded_aweme_ids or set()
        return [dict(c) for c in candidates if str(c.get("aweme_id") or "") not in excluded]

    def fetch_non_storeable_aweme_ids(self, candidate_ids: list[str]) -> set[str]:
        ids = [str(x) for x in candidate_ids if x]
        if not ids:
            return set()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT aweme_id
                FROM beauty.ai_beauty_candidates
                WHERE aweme_id = ANY(%s::text[])
                  AND candidate_status = ANY(%s)
                """,
                (ids, list(TERMINAL_STATUSES)),
            ).fetchall()
        return {str(r[0]) for r in rows}

    def fetch_active_pool(self, *, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT aweme_id, caption, hashtags, width, height, duration_seconds, source_stats,
                       candidate_status, priority_score, douyin_url, author_id, author_name,
                       discovered_at, last_seen_at
                FROM beauty.ai_beauty_candidates
                WHERE candidate_status = ANY(%s) AND douyin_url IS NOT NULL
                ORDER BY discovered_at DESC, id DESC
                LIMIT %s
                """,
                (list(ACTIVE_STATUSES), limit),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def mark_status(self, aweme_id: str, status: str, reason: str | None = None) -> None:
        assert_known_status(status)
        note_expr = "notes"
        params: dict[str, Any] = {"aweme_id": aweme_id, "status": status}
        if reason:
            note_expr = "concat_ws(E'\\n', NULLIF(notes, ''), %(reason)s::text)"
            params["reason"] = reason
        with self._connect() as conn:
            conn.execute(
                f"""
                UPDATE beauty.ai_beauty_candidates
                SET candidate_status = %(status)s,
                    notes = {note_expr}
                WHERE aweme_id = %(aweme_id)s
                """,
                params,
            )
            conn.commit()

    def mark_batch_selected(self, aweme_ids: list[str]) -> None:
        if not aweme_ids:
            return
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE beauty.ai_beauty_candidates
                SET candidate_status = %s, notes = COALESCE(notes, '')
                WHERE aweme_id = ANY(%s::text[])
                """,
                (BATCH_SELECTED_STATUS, aweme_ids),
            )
            conn.commit()

    def mark_archived(self, aweme_ids: list[str], reason: str) -> None:
        if not aweme_ids:
            return
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE beauty.ai_beauty_candidates
                SET candidate_status = %s,
                    notes = concat_ws(E'\n', NULLIF(notes, ''), %s::text)
                WHERE aweme_id = ANY(%s::text[])
                """,
                (ARCHIVED_STATUS, reason, aweme_ids),
            )
            conn.commit()

    def prune_archive_overflow(self, *, archive_limit: int) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                WITH ranked_archive AS (
                    SELECT aweme_id, row_number() OVER (ORDER BY priority_score DESC, last_seen_at DESC NULLS LAST, discovered_at DESC) AS rn
                    FROM beauty.ai_beauty_candidates
                    WHERE candidate_status = %s
                ), overflow AS (
                    SELECT aweme_id FROM ranked_archive WHERE rn > %s
                )
                UPDATE beauty.ai_beauty_candidates c
                SET candidate_status = %s,
                    notes = concat_ws(E'\n', NULLIF(c.notes, ''), 'Archive pruned: exceeded archived candidate cap.')
                FROM overflow
                WHERE c.aweme_id = overflow.aweme_id
                RETURNING c.aweme_id
                """,
                (ARCHIVED_STATUS, archive_limit, ARCHIVE_PRUNED_STATUS),
            ).fetchall()
            conn.commit()
        return [str(r[0]) for r in rows]

    def update_priority_scores(self, candidates: Iterable[dict[str, Any]]) -> int:
        count = 0
        with self._connect() as conn:
            for candidate in candidates:
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

    def upsert_search_candidates(self, candidates: list[dict[str, Any]], *, keyword: str, run_id: str | None = None) -> int:
        excluded = self.fetch_non_storeable_aweme_ids([str(c.get("aweme_id") or "") for c in candidates])
        candidates = self.filter_storeable_candidates(candidates, excluded_aweme_ids=excluded)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO beauty.ai_beauty_sources (source_type, source_value, last_checked_at)
                VALUES ('douyin_search', %s, now())
                ON CONFLICT (source_type, source_value) DO UPDATE SET last_checked_at = now()
                """,
                (keyword,),
            )
            count = 0
            for c in candidates:
                conn.execute(
                    """
                    INSERT INTO beauty.ai_beauty_candidates (
                        source_platform, source_type, source_value, aweme_id, douyin_url,
                        author_id, author_name, caption, hashtags, duration_seconds,
                        width, height, source_stats, last_seen_at, candidate_status, collection_run_id
                    ) VALUES (
                        'Douyin', 'douyin_search', %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, now(), 'new', %s
                    )
                    ON CONFLICT (aweme_id) DO UPDATE SET
                        douyin_url = EXCLUDED.douyin_url,
                        author_id = COALESCE(EXCLUDED.author_id, beauty.ai_beauty_candidates.author_id),
                        author_name = COALESCE(EXCLUDED.author_name, beauty.ai_beauty_candidates.author_name),
                        caption = COALESCE(NULLIF(EXCLUDED.caption, ''), beauty.ai_beauty_candidates.caption),
                        hashtags = COALESCE(EXCLUDED.hashtags, beauty.ai_beauty_candidates.hashtags),
                        duration_seconds = COALESCE(EXCLUDED.duration_seconds, beauty.ai_beauty_candidates.duration_seconds),
                        width = COALESCE(EXCLUDED.width, beauty.ai_beauty_candidates.width),
                        height = COALESCE(EXCLUDED.height, beauty.ai_beauty_candidates.height),
                        source_stats = COALESCE(EXCLUDED.source_stats, beauty.ai_beauty_candidates.source_stats),
                        last_seen_at = now(),
                        collection_run_id = EXCLUDED.collection_run_id
                    """,
                    (
                        keyword,
                        c["aweme_id"],
                        c["douyin_url"],
                        c.get("author_id"),
                        c.get("author_name"),
                        c.get("caption"),
                        c.get("hashtags"),
                        c.get("duration_seconds"),
                        c.get("width"),
                        c.get("height"),
                        json.dumps(c.get("source_stats") or {}, ensure_ascii=False),
                        run_id,
                    ),
                )
                count += 1
            conn.commit()
        return count


DEFAULT_CANDIDATE_REPOSITORY = CandidateRepository()
