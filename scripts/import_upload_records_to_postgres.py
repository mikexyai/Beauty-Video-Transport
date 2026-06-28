from __future__ import annotations

import csv
import re
from pathlib import Path

import psycopg
from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "upload_records.csv"
CRED_PATH = Path("C:/Project/Setup/postgresql/postgres-credentials.txt")
DB_NAME = "beauty"
TABLE_NAME = "upload_records"


def read_credentials(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key in {"host", "port", "database", "username", "password"}:
            out[key] = value
    required = {"host", "port", "database", "username", "password"}
    missing = required - set(out)
    if missing:
        raise SystemExit(f"Missing PostgreSQL credential fields: {sorted(missing)}")
    return out


def connect(dbname: str | None = None, *, autocommit: bool = False):
    c = read_credentials(CRED_PATH)
    # The credentials file may name an application DB that has not been created yet.
    # For admin/create-database operations, fall back to the built-in `postgres` DB.
    last_error = None
    for candidate in [dbname or c["database"], "postgres", "template1"]:
        try:
            return psycopg.connect(
                host=c["host"],
                port=int(c["port"]),
                dbname=candidate,
                user=c["username"],
                password=c["password"],
                autocommit=autocommit,
            )
        except psycopg.OperationalError as exc:
            last_error = exc
            if dbname is not None:
                break
    raise last_error


def ensure_database() -> str:
    try:
        with connect(autocommit=True) as conn:
            exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)).fetchone()
            if not exists:
                conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
                return "created"
            return "exists"
    except psycopg.errors.InsufficientPrivilege as exc:
        raise SystemExit(
            "Current PostgreSQL user does not have permission to CREATE DATABASE beauty. "
            "Grant CREATEDB or create it manually, then rerun this script."
        ) from exc


def ensure_schema(conn: psycopg.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id BIGSERIAL PRIMARY KEY,
            recorded_at TIMESTAMPTZ,
            source_platform TEXT NOT NULL,
            source_url TEXT,
            bvid TEXT,
            source_title TEXT,
            source_up TEXT,
            local_download_file TEXT,
            local_output_file TEXT,
            youtube_profile TEXT,
            youtube_channel_title TEXT,
            youtube_channel_handle TEXT,
            youtube_channel_id TEXT,
            youtube_video_id TEXT NOT NULL,
            youtube_url TEXT,
            youtube_title TEXT,
            youtube_privacy_status TEXT,
            notes TEXT,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {TABLE_NAME}_youtube_video_id_uidx "
        f"ON {TABLE_NAME} (youtube_video_id)"
    )
    conn.execute(
        f"CREATE INDEX IF NOT EXISTS {TABLE_NAME}_source_platform_bvid_idx "
        f"ON {TABLE_NAME} (source_platform, bvid)"
    )
    conn.execute(
        f"CREATE OR REPLACE VIEW records AS SELECT * FROM {TABLE_NAME} ORDER BY recorded_at DESC NULLS LAST, id DESC"
    )


def normalize_recorded_at(value: str) -> str | None:
    value = (value or "").strip()
    if not value:
        return None
    # Python isoformat strings in the CSV are already PostgreSQL-compatible.
    return value


def import_csv(conn: psycopg.Connection) -> tuple[int, int]:
    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found: {CSV_PATH}")
    rows = list(csv.DictReader(CSV_PATH.open("r", encoding="utf-8", newline="")))
    inserted_or_updated = 0
    for row in rows:
        vals = {
            "recorded_at": normalize_recorded_at(row.get("recorded_at", "")),
            "source_platform": row.get("source_platform") or "",
            "source_url": row.get("source_url") or None,
            "bvid": row.get("bvid") or None,
            "source_title": row.get("source_title") or None,
            "source_up": row.get("source_up") or None,
            "local_download_file": row.get("local_download_file") or None,
            "local_output_file": row.get("local_output_file") or None,
            "youtube_profile": row.get("youtube_profile") or None,
            "youtube_channel_title": row.get("youtube_channel_title") or None,
            "youtube_channel_handle": row.get("youtube_channel_handle") or None,
            "youtube_channel_id": row.get("youtube_channel_id") or None,
            "youtube_video_id": row.get("youtube_video_id") or "",
            "youtube_url": row.get("youtube_url") or None,
            "youtube_title": row.get("youtube_title") or None,
            "youtube_privacy_status": row.get("youtube_privacy_status") or None,
            "notes": row.get("notes") or None,
        }
        if not vals["youtube_video_id"]:
            continue
        conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                recorded_at, source_platform, source_url, bvid, source_title, source_up,
                local_download_file, local_output_file, youtube_profile, youtube_channel_title,
                youtube_channel_handle, youtube_channel_id, youtube_video_id, youtube_url,
                youtube_title, youtube_privacy_status, notes
            ) VALUES (
                %(recorded_at)s, %(source_platform)s, %(source_url)s, %(bvid)s, %(source_title)s, %(source_up)s,
                %(local_download_file)s, %(local_output_file)s, %(youtube_profile)s, %(youtube_channel_title)s,
                %(youtube_channel_handle)s, %(youtube_channel_id)s, %(youtube_video_id)s, %(youtube_url)s,
                %(youtube_title)s, %(youtube_privacy_status)s, %(notes)s
            )
            ON CONFLICT (youtube_video_id) DO UPDATE SET
                recorded_at = EXCLUDED.recorded_at,
                source_platform = EXCLUDED.source_platform,
                source_url = EXCLUDED.source_url,
                bvid = EXCLUDED.bvid,
                source_title = EXCLUDED.source_title,
                source_up = EXCLUDED.source_up,
                local_download_file = EXCLUDED.local_download_file,
                local_output_file = EXCLUDED.local_output_file,
                youtube_profile = EXCLUDED.youtube_profile,
                youtube_channel_title = EXCLUDED.youtube_channel_title,
                youtube_channel_handle = EXCLUDED.youtube_channel_handle,
                youtube_channel_id = EXCLUDED.youtube_channel_id,
                youtube_url = EXCLUDED.youtube_url,
                youtube_title = EXCLUDED.youtube_title,
                youtube_privacy_status = EXCLUDED.youtube_privacy_status,
                notes = EXCLUDED.notes,
                imported_at = now()
            """,
            vals,
        )
        inserted_or_updated += 1
    total = conn.execute(f"SELECT count(*) FROM {TABLE_NAME}").fetchone()[0]
    return inserted_or_updated, total


def main() -> None:
    db_status = ensure_database()
    with connect(DB_NAME) as conn:
        ensure_schema(conn)
        imported, total = import_csv(conn)
        by_platform = conn.execute(
            f"SELECT source_platform, count(*) FROM {TABLE_NAME} GROUP BY source_platform ORDER BY source_platform"
        ).fetchall()
        latest = conn.execute(
            f"SELECT source_platform, bvid, youtube_video_id, youtube_title FROM {TABLE_NAME} "
            "ORDER BY recorded_at DESC NULLS LAST, id DESC LIMIT 5"
        ).fetchall()
        conn.commit()
    print({
        "database": DB_NAME,
        "database_status": db_status,
        "table": TABLE_NAME,
        "csv_rows_imported_or_updated": imported,
        "table_total_rows": total,
        "counts_by_platform": by_platform,
        "latest_5": latest,
    })


if __name__ == "__main__":
    main()
