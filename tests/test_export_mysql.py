import sqlite3

from job_archive.export_mysql import TABLE_COLUMNS, build_upsert_sql, copy_table


class FakeMySQLCursor:
    def __init__(self) -> None:
        self.calls = []

    def executemany(self, sql, rows) -> None:
        self.calls.append((sql, rows))


def test_build_upsert_sql_does_not_update_primary_key() -> None:
    sql = build_upsert_sql("example", ("id", "name"))

    assert "VALUES (%s, %s)" in sql
    assert "`name` = VALUES(`name`)" in sql
    assert "`id` = VALUES(`id`)" not in sql


def test_copy_table_uses_batches() -> None:
    source = sqlite3.connect(":memory:")
    source.execute(
        """
        CREATE TABLE crawl_runs (
            id INTEGER, source TEXT, started_at TEXT, finished_at TEXT,
            status TEXT, pages_fetched INTEGER, postings_seen INTEGER,
            postings_created INTEGER, postings_updated INTEGER, error_message TEXT
        )
        """
    )
    source.executemany(
        "INSERT INTO crawl_runs VALUES (?, 'kofia', 'now', NULL, 'success', 1, 1, 1, 0, NULL)",
        [(1,), (2,), (3,)],
    )
    target = FakeMySQLCursor()

    copied = copy_table(source, target, "crawl_runs", batch_size=2)

    assert copied == 3
    assert [len(rows) for _, rows in target.calls] == [2, 1]
    source.close()


def test_mysql_postings_include_category_columns() -> None:
    columns = TABLE_COLUMNS["postings"]

    assert "company_category" in columns
    assert "job_category_1" in columns
    assert "job_category_2" in columns
