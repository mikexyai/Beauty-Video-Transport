from __future__ import annotations

from pathlib import Path

import sys

PROJECT_BOOTSTRAP_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_BOOTSTRAP_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_BOOTSTRAP_ROOT))

from scripts.ai_beauty.db import PROJECT_ROOT, connect

SCHEMA_PATH = PROJECT_ROOT / "sql" / "ai_beauty_schema.sql"
EXPECTED_TABLES = [
    "ai_beauty_candidates",
    "ai_beauty_run_logs",
    "ai_beauty_screenings",
    "ai_beauty_sources",
    "ai_beauty_strategy_state",
    "ai_beauty_uploads",
    "ai_beauty_video_metrics",
]


def init_schema(schema_path: Path = SCHEMA_PATH) -> list[str]:
    sql = schema_path.read_text(encoding="utf-8")
    with connect() as conn:
        conn.execute(sql)
        rows = conn.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'beauty' AND table_name LIKE 'ai_beauty_%'
            ORDER BY table_name
            """
        ).fetchall()
        conn.commit()
    return [r[0] for r in rows]


def main() -> int:
    tables = init_schema()
    missing = sorted(set(EXPECTED_TABLES) - set(tables))
    print({"schema": "beauty", "tables": tables, "missing": missing})
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
