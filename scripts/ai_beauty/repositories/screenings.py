from __future__ import annotations

from collections.abc import Callable
from typing import Any

from scripts.ai_beauty.db import connect


class ScreeningRepository:
    def __init__(self, connect_fn: Callable[[], Any] | None = connect) -> None:
        self.connect_fn = connect_fn

    def insert_screening(self, params: dict[str, Any]) -> int:
        if self.connect_fn is None:
            raise RuntimeError("ScreeningRepository requires a connect_fn for database operations")
        with self.connect_fn() as conn:
            row = conn.execute(
                """
                INSERT INTO beauty.ai_beauty_screenings (
                    aweme_id, model_name, contact_sheet_path, is_beauty_content,
                    suitable_for_ai_beauty, visible_minor_risk, low_quality, obvious_watermark,
                    duplicate_risk, sensuality_level, explicitness_level, content_type,
                    visual_style, safety_json, visual_labels_json, decision, skip_reason,
                    recommended_title, recommended_tags, selection_reason
                ) VALUES (
                    %(aweme_id)s, %(model_name)s, %(contact_sheet_path)s, %(is_beauty_content)s,
                    %(suitable_for_ai_beauty)s, %(visible_minor_risk)s, %(low_quality)s, %(obvious_watermark)s,
                    %(duplicate_risk)s, %(sensuality_level)s, %(explicitness_level)s, %(content_type)s,
                    %(visual_style)s, %(safety_json)s, %(visual_labels_json)s, %(decision)s, %(skip_reason)s,
                    %(recommended_title)s, %(recommended_tags)s, %(selection_reason)s
                ) RETURNING id
                """,
                params,
            ).fetchone()
            conn.commit()
        return int(row[0])


screening_repository = ScreeningRepository()
