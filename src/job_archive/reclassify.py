"""기존 SQLite 공고의 회사·직무 카테고리를 다시 계산한다."""

import argparse
from pathlib import Path

from job_archive.classify import classify_categories
from job_archive.database import connect


DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "jobs.sqlite3"


def reclassify(db_path: Path) -> int:
    connection = connect(db_path)
    try:
        rows = connection.execute(
            "SELECT id, company, title, body_text FROM postings ORDER BY id"
        ).fetchall()
        for row in rows:
            categories = classify_categories(
                row["company"], row["title"], row["body_text"] or ""
            )
            connection.execute(
                """
                UPDATE postings SET
                    company_category = ?, job_category_1 = ?, job_category_2 = ?
                WHERE id = ?
                """,
                (
                    categories.company_category,
                    categories.job_category_1,
                    categories.job_category_2,
                    row["id"],
                ),
            )
        connection.commit()
        return len(rows)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="기존 공고 회사·직무 카테고리 재분류")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    args = parser.parse_args()
    count = reclassify(args.db.resolve())
    print(f"재분류 완료: {count}개 공고")


if __name__ == "__main__":
    main()
