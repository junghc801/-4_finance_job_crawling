import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate_posting_categories(connection)
    return connection


def _migrate_posting_categories(connection: sqlite3.Connection) -> None:
    existing = {
        row["name"] for row in connection.execute("PRAGMA table_info(postings)")
    }
    migrations = {
        "company_category": "TEXT NOT NULL DEFAULT 'other'",
        "job_category_1": "TEXT NOT NULL DEFAULT 'other'",
        "job_category_2": "TEXT",
    }
    for column, definition in migrations.items():
        if column not in existing:
            connection.execute(
                f'ALTER TABLE postings ADD COLUMN "{column}" {definition}'
            )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_postings_company_category "
        "ON postings(company_category)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_postings_job_category_1 "
        "ON postings(job_category_1)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_postings_job_category_2 "
        "ON postings(job_category_2)"
    )
    connection.commit()


def begin_run(connection: sqlite3.Connection, source: str) -> int:
    cursor = connection.execute(
        "INSERT INTO crawl_runs(source, started_at, status) VALUES (?, ?, 'running')",
        (source, utc_now()),
    )
    connection.commit()
    return int(cursor.lastrowid)


def finish_run(connection: sqlite3.Connection, run_id: int, status: str, **values: object) -> None:
    allowed = {
        "pages_fetched",
        "postings_seen",
        "postings_created",
        "postings_updated",
        "error_message",
    }
    updates = {key: value for key, value in values.items() if key in allowed}
    updates.update(finished_at=utc_now(), status=status)
    assignments = ", ".join(f"{key} = ?" for key in updates)
    connection.execute(
        f"UPDATE crawl_runs SET {assignments} WHERE id = ?",
        (*updates.values(), run_id),
    )
    connection.commit()


def upsert_posting(connection: sqlite3.Connection, posting: dict, raw_html: str) -> str:
    now = utc_now()
    existing = connection.execute(
        "SELECT id, content_hash FROM postings WHERE source = ? AND external_id = ?",
        (posting["source"], posting["external_id"]),
    ).fetchone()

    values = (
        posting["source_url"],
        posting.get("company"),
        posting.get("company_category", "other"),
        posting["title"],
        posting.get("body_text"),
        posting.get("posted_at"),
        posting.get("deadline_at"),
        posting["audience"],
        posting.get("employment_type"),
        posting.get("classification_note"),
        posting.get("job_category_1", "other"),
        posting.get("job_category_2"),
        json.dumps(posting.get("attachments", []), ensure_ascii=False),
        posting["content_hash"],
    )

    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO postings (
                source, external_id, source_url, company, company_category,
                title, body_text, posted_at, deadline_at, audience, employment_type,
                classification_note, job_category_1, job_category_2,
                attachments_json, first_seen_at, last_seen_at, last_changed_at,
                content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                posting["source"],
                posting["external_id"],
                *values[:-1],
                now,
                now,
                now,
                posting["content_hash"],
            ),
        )
        posting_id = int(cursor.lastrowid)
        result = "created"
    elif existing["content_hash"] == posting["content_hash"]:
        connection.execute(
            """
            UPDATE postings SET
                company = ?, company_category = ?, audience = ?,
                employment_type = ?, classification_note = ?,
                job_category_1 = ?, job_category_2 = ?, last_seen_at = ?
            WHERE id = ?
            """,
            (
                posting.get("company"),
                posting.get("company_category", "other"),
                posting["audience"],
                posting.get("employment_type"),
                posting.get("classification_note"),
                posting.get("job_category_1", "other"),
                posting.get("job_category_2"),
                now,
                existing["id"],
            ),
        )
        connection.commit()
        return "unchanged"
    else:
        posting_id = int(existing["id"])
        connection.execute(
            """
            UPDATE postings SET
                source_url = ?, company = ?, company_category = ?, title = ?, body_text = ?,
                posted_at = ?, deadline_at = ?, audience = ?, employment_type = ?,
                classification_note = ?, job_category_1 = ?, job_category_2 = ?,
                attachments_json = ?, content_hash = ?,
                last_seen_at = ?, last_changed_at = ?
            WHERE id = ?
            """,
            (*values, now, now, posting_id),
        )
        result = "updated"

    connection.execute(
        """
        INSERT OR IGNORE INTO posting_snapshots
            (posting_id, captured_at, content_hash, title, body_text, raw_html)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            posting_id,
            now,
            posting["content_hash"],
            posting["title"],
            posting.get("body_text"),
            raw_html,
        ),
    )
    connection.commit()
    return result
