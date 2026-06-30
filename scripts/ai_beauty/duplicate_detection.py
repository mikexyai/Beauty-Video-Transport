from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from PIL import Image

from scripts.ai_beauty.db import connect


def normalize_duplicate_text(value: str | None) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[#@]", " ", text)
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_similarity(a: str | None, b: str | None) -> float:
    na = normalize_duplicate_text(a)
    nb = normalize_duplicate_text(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def hamming_distance(a: int, b: int) -> int:
    return int(a ^ b).bit_count()


def average_hash(image_path: str | Path, *, hash_size: int = 8) -> int:
    img = Image.open(image_path).convert("L").resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= avg)
    return value


def assess_text_duplicate_risk(candidate: dict[str, Any], previous_uploads: list[dict[str, Any]]) -> dict[str, Any]:
    caption = candidate.get("caption") or candidate.get("title") or ""
    author = normalize_duplicate_text(candidate.get("author_name"))
    signals: list[dict[str, Any]] = []
    max_similarity = 0.0
    for upload in previous_uploads:
        title = upload.get("title") or ""
        sim = text_similarity(caption, title)
        max_similarity = max(max_similarity, sim)
        if sim >= 0.92:
            signals.append({"type": "title_caption_similarity", "similarity": round(sim, 4), "matched_title": title})
        elif sim >= 0.78:
            signals.append({"type": "possible_title_caption_similarity", "similarity": round(sim, 4), "matched_title": title})
        upload_author = normalize_duplicate_text(upload.get("author_name"))
        if author and upload_author and author == upload_author and sim >= 0.65:
            signals.append({"type": "author_caption_similarity", "similarity": round(sim, 4), "author": author})
    high = any(s["type"] in {"title_caption_similarity", "author_caption_similarity"} for s in signals)
    medium = any(s["type"].startswith("possible_") for s in signals)
    risk = "high" if high else "medium" if medium else "low"
    return {"risk": risk, "max_similarity": round(max_similarity, 4), "signals": signals}


def fetch_recent_uploads(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT aweme_id, title, tags
            FROM beauty.ai_beauty_uploads
            ORDER BY uploaded_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def assess_candidate_against_recent_uploads(candidate: dict[str, Any], *, limit: int = 50) -> dict[str, Any]:
    return assess_text_duplicate_risk(candidate, fetch_recent_uploads(limit=limit))


def main() -> int:
    parser = argparse.ArgumentParser(description="Assess AI Beauty duplicate risk for a candidate JSON object using text signals.")
    parser.add_argument("--candidate-json", help="Candidate JSON string")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    if args.candidate_json:
        candidate = json.loads(args.candidate_json)
    else:
        candidate = json.load(sys.stdin)  # type: ignore[name-defined]
    result = assess_candidate_against_recent_uploads(candidate, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
