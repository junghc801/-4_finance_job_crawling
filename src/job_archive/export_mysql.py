"""SQLite 채용공고 데이터를 MySQL로 복사하는 명령행 도구."""

import argparse
import getpass
import os
import sqlite3
from collections.abc import Sequence
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = PROJECT_ROOT / "data" / "jobs.sqlite3"

TABLE_COLUMNS = {
    "postings": (
        "id", "source", "external_id", "source_url", "company", "title",
        "body_text", "posted_at", "deadline_at", "audience", "employment_type",
        "classification_note", "manual_audience", "attachments_json",
        "first_seen_at", "last_seen_at", "last_changed_at", "content_hash",
    ),
    "posting_snapshots": (
        "id", "posting_id", "captured_at", "content_hash", "title", "body_text",
        "raw_html",
    ),
    "crawl_runs": (
        "id", "source", "started_at", "finished_at", "status", "pages_fetched",
        "postings_seen", "postings_created", "postings_updated", "error_message",
    ),
}

MYSQL_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS postings (
        id BIGINT PRIMARY KEY,
        source VARCHAR(64) NOT NULL,
        external_id VARCHAR(191) NOT NULL,
        source_url TEXT NOT NULL,
        company VARCHAR(255),
        title TEXT NOT NULL,
        body_text LONGTEXT,
        posted_at VARCHAR(10),
        deadline_at VARCHAR(10),
        audience VARCHAR(32) NOT NULL DEFAULT 'unknown',
        employment_type VARCHAR(32),
        classification_note TEXT,
        manual_audience VARCHAR(32),
        attachments_json LONGTEXT NOT NULL,
        first_seen_at VARCHAR(40) NOT NULL,
        last_seen_at VARCHAR(40) NOT NULL,
        last_changed_at VARCHAR(40) NOT NULL,
        content_hash CHAR(64) NOT NULL,
        UNIQUE KEY uq_postings_source_external (source, external_id),
        KEY idx_postings_posted_at (posted_at),
        KEY idx_postings_company (company),
        KEY idx_postings_audience (audience)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS posting_snapshots (
        id BIGINT PRIMARY KEY,
        posting_id BIGINT NOT NULL,
        captured_at VARCHAR(40) NOT NULL,
        content_hash CHAR(64) NOT NULL,
        title TEXT NOT NULL,
        body_text LONGTEXT,
        raw_html LONGTEXT,
        UNIQUE KEY uq_snapshot_posting_hash (posting_id, content_hash),
        CONSTRAINT fk_snapshots_posting
            FOREIGN KEY (posting_id) REFERENCES postings(id)
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS crawl_runs (
        id BIGINT PRIMARY KEY,
        source VARCHAR(64) NOT NULL,
        started_at VARCHAR(40) NOT NULL,
        finished_at VARCHAR(40),
        status VARCHAR(32) NOT NULL,
        pages_fetched INT NOT NULL DEFAULT 0,
        postings_seen INT NOT NULL DEFAULT 0,
        postings_created INT NOT NULL DEFAULT 0,
        postings_updated INT NOT NULL DEFAULT 0,
        error_message LONGTEXT
    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
)


def build_upsert_sql(table: str, columns: Sequence[str]) -> str:
    quoted = ", ".join(f"`{column}`" for column in columns)
    placeholders = ", ".join("%s" for _ in columns)
    updates = ", ".join(
        f"`{column}` = VALUES(`{column}`)" for column in columns if column != "id"
    )
    return (
        f"INSERT INTO `{table}` ({quoted}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )


def copy_table(
    sqlite_connection: sqlite3.Connection,
    mysql_cursor,
    table: str,
    batch_size: int,
) -> int:
    columns = TABLE_COLUMNS[table]
    column_sql = ", ".join(f'"{column}"' for column in columns)
    source_cursor = sqlite_connection.execute(
        f'SELECT {column_sql} FROM "{table}" ORDER BY "id"'
    )
    upsert_sql = build_upsert_sql(table, columns)
    copied = 0

    while rows := source_cursor.fetchmany(batch_size):
        mysql_cursor.executemany(upsert_sql, [tuple(row) for row in rows])
        copied += len(rows)
    return copied


def copy_to_mysql(
    sqlite_path: Path,
    mysql_config: dict,
    batch_size: int = 500,
) -> dict[str, int]:
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite 파일을 찾을 수 없습니다: {sqlite_path}")

    try:
        import pymysql
    except ImportError as error:
        raise RuntimeError("PyMySQL이 없습니다. 먼저 pip install -r requirements.txt를 실행하세요.") from error

    sqlite_connection = sqlite3.connect(sqlite_path)
    sqlite_connection.row_factory = sqlite3.Row
    mysql_connection = pymysql.connect(
        **mysql_config,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=10,
        read_timeout=60,
        write_timeout=60,
    )

    counts: dict[str, int] = {}
    try:
        with mysql_connection.cursor() as mysql_cursor:
            for statement in MYSQL_SCHEMA:
                mysql_cursor.execute(statement)
            for table in TABLE_COLUMNS:
                counts[table] = copy_table(
                    sqlite_connection, mysql_cursor, table, batch_size
                )
        mysql_connection.commit()
        return counts
    except Exception:
        mysql_connection.rollback()
        raise
    finally:
        sqlite_connection.close()
        mysql_connection.close()


def _required(value: str | None, name: str) -> str:
    if value:
        return value
    raise SystemExit(f"{name} 값이 필요합니다.")


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite 채용공고 데이터를 MySQL로 복사")
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--host", default=os.getenv("MYSQL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MYSQL_PORT", "3306")))
    parser.add_argument("--user", default=os.getenv("MYSQL_USER"))
    parser.add_argument("--database", default=os.getenv("MYSQL_DATABASE"))
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size는 1 이상이어야 합니다.")

    password = os.getenv("MYSQL_PASSWORD")
    if password is None:
        password = getpass.getpass("MySQL password: ")

    config = {
        "host": args.host,
        "port": args.port,
        "user": _required(args.user, "--user 또는 MYSQL_USER"),
        "password": password,
        "database": _required(args.database, "--database 또는 MYSQL_DATABASE"),
    }
    counts = copy_to_mysql(args.sqlite.resolve(), config, args.batch_size)
    print(
        "MySQL 복사 완료: "
        + ", ".join(f"{table} {count}행" for table, count in counts.items())
    )


if __name__ == "__main__":
    main()

