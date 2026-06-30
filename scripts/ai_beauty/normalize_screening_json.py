from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DECISIONS = {"approved", "skipped", "review", "failed"}
LEVELS = {"none", "mild", "medium", "high", "unknown"}
DUPLICATE_RISKS = {"low", "medium", "high", "unknown"}

FIELD_ALIASES = {
    "title": "recommended_title",
    "recommended_english_title": "recommended_title",
    "youtube_title": "recommended_title",
    "tags": "recommended_tags",
    "youtube_tags": "recommended_tags",
    "minor_risk": "visible_minor_risk",
    "watermark": "obvious_watermark",
    "reason": "selection_reason",
}


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1)
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            value, _end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Could not extract JSON object from vision output")


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"true", "yes", "y", "1", "risk", "high", "medium", "low_to_medium", "unclear"}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        if "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
        return [value.strip()] if value.strip() else []
    return [str(value).strip()]


def _enum(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text in allowed:
        return text
    if text in {"low_to_medium", "moderate"}:
        return "medium" if "medium" in allowed else default
    return default


def _looks_like_long_compilation(data: dict[str, Any]) -> bool:
    duration = data.get("duration_seconds") or data.get("duration")
    try:
        duration_f = float(duration or 0)
    except (TypeError, ValueError):
        duration_f = 0.0
    text = " ".join(_as_list(data.get("content_type")) + _as_list(data.get("visual_style")) + [str(data.get("selection_reason") or ""), str(data.get("skip_reason") or ""), str(data.get("recommended_title") or "")]).lower()
    has_compilation_signal = any(word in text for word in ["compilation", "ranking", "top-10", "top 10", "montage", "合集", "榜单"])
    return duration_f >= 180 and has_compilation_signal


def normalize_screening(data: dict[str, Any], *, contact_sheet_path: str | None = None) -> dict[str, Any]:
    normalized: dict[str, Any] = dict(data)
    for old, new in FIELD_ALIASES.items():
        if old in normalized and new not in normalized:
            normalized[new] = normalized[old]

    if contact_sheet_path:
        normalized["contact_sheet_path"] = contact_sheet_path

    for key in ["is_beauty_content", "suitable_for_ai_beauty", "visible_minor_risk", "low_quality", "obvious_watermark"]:
        normalized[key] = _as_bool(normalized.get(key))

    normalized["duplicate_risk"] = _enum(normalized.get("duplicate_risk"), DUPLICATE_RISKS, "unknown")
    normalized["sensuality_level"] = _enum(normalized.get("sensuality_level"), LEVELS, "unknown")
    normalized["explicitness_level"] = _enum(normalized.get("explicitness_level"), LEVELS, "unknown")
    normalized["content_type"] = _as_list(normalized.get("content_type"))
    normalized["visual_style"] = _as_list(normalized.get("visual_style"))
    normalized["motion_type"] = _as_list(normalized.get("motion_type"))
    normalized["recommended_tags"] = _as_list(normalized.get("recommended_tags"))[:5]
    normalized["recommended_title"] = str(normalized.get("recommended_title") or "").strip()
    normalized["selection_reason"] = str(normalized.get("selection_reason") or "").strip()
    normalized["skip_reason"] = str(normalized.get("skip_reason") or "").strip()

    decision = str(normalized.get("decision") or "review").strip().lower()
    if decision not in DECISIONS:
        decision = "review"

    if _looks_like_long_compilation(normalized):
        decision = "skipped"
        normalized["suitable_for_ai_beauty"] = False
        if not normalized["skip_reason"]:
            normalized["skip_reason"] = "Long compilation/ranking montage is unsuitable for AI Beauty short-form upload."

    if normalized["visible_minor_risk"] and decision == "approved":
        decision = "review"
        if not normalized["skip_reason"]:
            normalized["skip_reason"] = "visible_minor_risk=true requires manual review before upload."

    if decision == "approved" and (not normalized["recommended_title"] or not normalized["recommended_tags"]):
        decision = "review"
        if not normalized["skip_reason"]:
            normalized["skip_reason"] = "Approved screening lacked required title or tags."

    normalized["decision"] = decision
    return normalized


def normalize_text(raw: str, *, contact_sheet_path: str | None = None) -> dict[str, Any]:
    return normalize_screening(extract_json_object(raw), contact_sheet_path=contact_sheet_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize AI Beauty vision screening JSON before DB recording.")
    parser.add_argument("input", type=Path, help="Raw vision output text/JSON file")
    parser.add_argument("--contact-sheet-path")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    normalized = normalize_text(args.input.read_text(encoding="utf-8"), contact_sheet_path=args.contact_sheet_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(args.out), "decision": normalized.get("decision")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
