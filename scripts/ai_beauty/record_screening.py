from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import sys

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.repositories.screenings import screening_repository

VALID_DECISIONS = {"approved", "skipped", "review", "failed"}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def validate_screening(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)
    decision = str(normalized.get("decision", "")).strip().lower()
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")
    normalized["decision"] = decision
    normalized["content_type"] = _as_list(normalized.get("content_type"))
    normalized["visual_style"] = _as_list(normalized.get("visual_style"))
    normalized["recommended_tags"] = _as_list(normalized.get("recommended_tags"))
    if len(normalized["recommended_tags"]) > 5:
        raise ValueError("recommended_tags must contain no more than 5 tags")
    if decision == "approved":
        title = str(normalized.get("recommended_title") or "").strip()
        if not title:
            raise ValueError("approved screening requires recommended_title")
        if not normalized["recommended_tags"]:
            raise ValueError("approved screening requires at least one recommended tag")
        if normalized.get("visible_minor_risk") is True:
            raise ValueError("visible_minor_risk candidates cannot be approved")
    return normalized


def build_screening_insert_params(aweme_id: str, data: dict[str, Any], *, model_name: str | None = None) -> dict[str, Any]:
    d = validate_screening(data)
    return {
        "aweme_id": aweme_id,
        "model_name": model_name or d.get("model_name"),
        "contact_sheet_path": d.get("contact_sheet_path"),
        "is_beauty_content": d.get("is_beauty_content"),
        "suitable_for_ai_beauty": d.get("suitable_for_ai_beauty"),
        "visible_minor_risk": d.get("visible_minor_risk"),
        "low_quality": d.get("low_quality"),
        "obvious_watermark": d.get("obvious_watermark"),
        "duplicate_risk": d.get("duplicate_risk"),
        "sensuality_level": d.get("sensuality_level"),
        "explicitness_level": d.get("explicitness_level"),
        "content_type": d.get("content_type"),
        "visual_style": d.get("visual_style"),
        "safety_json": json.dumps(d.get("safety_json", {}), ensure_ascii=False),
        "visual_labels_json": json.dumps(d.get("visual_labels_json", d), ensure_ascii=False),
        "decision": d.get("decision"),
        "skip_reason": d.get("skip_reason"),
        "recommended_title": d.get("recommended_title"),
        "recommended_tags": d.get("recommended_tags"),
        "selection_reason": d.get("selection_reason"),
    }


def record_screening(aweme_id: str, data: dict[str, Any], *, model_name: str | None = None) -> int:
    params = build_screening_insert_params(aweme_id, data, model_name=model_name)
    return screening_repository.insert_screening(params)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record an AI Beauty visual screening JSON result.")
    parser.add_argument("--aweme-id", required=True)
    parser.add_argument("--json", required=True, type=Path)
    parser.add_argument("--model-name")
    args = parser.parse_args()
    data = json.loads(args.json.read_text(encoding="utf-8"))
    screening_id = record_screening(args.aweme_id, data, model_name=args.model_name)
    print({"screening_id": screening_id, "aweme_id": args.aweme_id})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
