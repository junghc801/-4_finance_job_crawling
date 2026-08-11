from job_archive.database import connect
from job_archive.reclassify import reclassify


def test_reclassify_updates_existing_posting(tmp_path) -> None:
    db_path = tmp_path / "test.sqlite3"
    connection = connect(db_path)
    connection.execute(
        """
        INSERT INTO postings (
            source, external_id, source_url, company, title, body_text,
            first_seen_at, last_seen_at, last_changed_at, content_hash
        ) VALUES (
            'kofia', '1', 'https://example.com', '테스트증권',
            '[테스트증권] 퀀트 리서치 인턴', '데이터 분석 업무',
            'now', 'now', 'now', 'hash'
        )
        """
    )
    connection.commit()
    connection.close()

    assert reclassify(db_path) == 1

    connection = connect(db_path)
    row = connection.execute(
        "SELECT company_category, job_category_1, job_category_2 FROM postings"
    ).fetchone()
    assert tuple(row) == ("securities", "quant_data", "research")
    connection.close()
