from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import connect
from scripts.ai_beauty.state import ALL_CANDIDATE_STATUSES

CONSTRAINT_NAME = "ai_beauty_candidates_status_check"


def candidate_status_allowed_values_sql() -> str:
    return ", ".join(sql_literal(status) for status in ALL_CANDIDATE_STATUSES)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_candidate_status_constraint_sql() -> str:
    allowed = candidate_status_allowed_values_sql()
    return f"""
ALTER TABLE beauty.ai_beauty_candidates
DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME};

ALTER TABLE beauty.ai_beauty_candidates
ADD CONSTRAINT {CONSTRAINT_NAME}
CHECK (candidate_status IN ({allowed}));
""".strip()


def build_candidate_status_constraint_rollback_sql() -> str:
    return f"""
ALTER TABLE beauty.ai_beauty_candidates
DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME};
""".strip()


def invalid_statuses(rows: Iterable[tuple[str, int]]) -> dict[str, int]:
    allowed = set(ALL_CANDIDATE_STATUSES)
    return {str(status): int(count) for status, count in rows if str(status) not in allowed}


def fetch_status_counts() -> list[tuple[str, int]]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT candidate_status, count(*)
            FROM beauty.ai_beauty_candidates
            GROUP BY candidate_status
            ORDER BY candidate_status
            """
        ).fetchall()


def fetch_constraint_defs() -> list[tuple[str, str]]:
    with connect() as conn:
        return conn.execute(
            """
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'beauty'
              AND t.relname = 'ai_beauty_candidates'
              AND c.contype = 'c'
              AND conname = %s
            ORDER BY conname
            """,
            (CONSTRAINT_NAME,),
        ).fetchall()


def apply_constraint() -> dict[str, object]:
    counts = fetch_status_counts()
    invalid = invalid_statuses(counts)
    if invalid:
        raise RuntimeError(f"Cannot add candidate status constraint; invalid statuses exist: {invalid}")
    sql = build_candidate_status_constraint_sql()
    with connect() as conn:
        conn.execute(sql)
        conn.commit()
    return {
        "applied": True,
        "constraint": CONSTRAINT_NAME,
        "status_counts": [{"status": s, "count": c} for s, c in counts],
        "constraints": [{"name": n, "definition": d} for n, d in fetch_constraint_defs()],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Add/check AI Beauty candidate_status DB constraint.")
    parser.add_argument("--dry-run", action="store_true", help="Print SQL and current status validity without applying")
    parser.add_argument("--apply", action="store_true", help="Apply the constraint if current statuses are valid")
    args = parser.parse_args()
    counts = fetch_status_counts()
    invalid = invalid_statuses(counts)
    if args.dry_run or not args.apply:
        print(json.dumps({
            "dry_run": True,
            "constraint": CONSTRAINT_NAME,
            "valid": not invalid,
            "invalid_statuses": invalid,
            "status_counts": [{"status": s, "count": c} for s, c in counts],
            "sql": build_candidate_status_constraint_sql(),
            "existing_constraints": [{"name": n, "definition": d} for n, d in fetch_constraint_defs()],
        }, ensure_ascii=False, indent=2))
        return 1 if invalid else 0
    print(json.dumps(apply_constraint(), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
