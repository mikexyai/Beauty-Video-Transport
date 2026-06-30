from __future__ import annotations

import argparse
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import sys

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import connect

AWEME_RE = re.compile(r"(?:/video/|modal_id=)(\d{10,})")


@dataclass(frozen=True)
class CandidateUrl:
    url: str
    aweme_id: str


def extract_aweme_id(url: str) -> str | None:
    match = AWEME_RE.search(url)
    if match:
        return match.group(1)
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("modal_id", "aweme_id", "item_id"):
        vals = query.get(key)
        if vals and vals[0].isdigit():
            return vals[0]
    path_digits = re.findall(r"\d{10,}", parsed.path)
    return path_digits[-1] if path_digits else None


def resolve_short_url(url: str, timeout: int = 10) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
    with urlopen(req, timeout=timeout) as resp:
        return resp.geturl()


def read_url_file(path: Path, *, resolve_short: bool = True) -> tuple[list[CandidateUrl], list[dict[str, str]]]:
    candidates: list[CandidateUrl] = []
    errors: list[dict[str, str]] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        url = line
        aweme_id = extract_aweme_id(url)
        if not aweme_id and resolve_short:
            try:
                resolved = resolve_short_url(url)
                aweme_id = extract_aweme_id(resolved)
                url = resolved
            except Exception as exc:  # network resolution is best-effort
                errors.append({"line": str(lineno), "url": line, "error": f"resolve failed: {exc}"})
                continue
        if not aweme_id:
            errors.append({"line": str(lineno), "url": line, "error": "could not extract aweme_id"})
            continue
        candidates.append(CandidateUrl(url=url, aweme_id=aweme_id))
    return candidates, errors


def upsert_candidates(candidates: list[CandidateUrl], *, source_type: str, source_value: str, run_id: str) -> int:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO beauty.ai_beauty_sources (source_type, source_value, last_checked_at)
            VALUES (%s, %s, now())
            ON CONFLICT (source_type, source_value) DO UPDATE SET last_checked_at = now()
            """,
            (source_type, source_value),
        )
        count = 0
        for c in candidates:
            conn.execute(
                """
                INSERT INTO beauty.ai_beauty_candidates (
                    source_platform, source_type, source_value, aweme_id, douyin_url,
                    last_seen_at, candidate_status, collection_run_id
                ) VALUES ('Douyin', %s, %s, %s, %s, now(), 'new', %s)
                ON CONFLICT (aweme_id) DO UPDATE SET
                    douyin_url = EXCLUDED.douyin_url,
                    source_type = EXCLUDED.source_type,
                    source_value = EXCLUDED.source_value,
                    last_seen_at = now(),
                    collection_run_id = EXCLUDED.collection_run_id
                """,
                (source_type, source_value, c.aweme_id, c.url, run_id),
            )
            count += 1
        conn.execute(
            """
            INSERT INTO beauty.ai_beauty_run_logs (
                run_id, job_type, finished_at, status, candidates_found, summary_json
            ) VALUES (%s, 'collect_urls', now(), 'completed', %s, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (run_id, count, json.dumps({"source_type": source_type, "source_value": source_value}, ensure_ascii=False)),
        )
        conn.commit()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect AI Beauty Douyin candidates from a URL list without Chrome/CDP.")
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--source-type", default="url_list")
    parser.add_argument("--source-value", default="manual")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-resolve-short", action="store_true")
    args = parser.parse_args()

    candidates, errors = read_url_file(args.file, resolve_short=not args.no_resolve_short)
    run_id = f"collect_urls_{uuid.uuid4().hex}"
    if args.dry_run:
        print({"dry_run": True, "candidates": [c.__dict__ for c in candidates], "errors": errors})
        return 0 if candidates else 1
    inserted = upsert_candidates(candidates, source_type=args.source_type, source_value=args.source_value, run_id=run_id)
    print({"run_id": run_id, "inserted_or_updated": inserted, "errors": errors})
    return 0 if inserted else 1


if __name__ == "__main__":
    raise SystemExit(main())
