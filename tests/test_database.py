import hashlib

from job_archive.database import connect, upsert_posting


def make_posting(body: str) -> dict:
    digest = hashlib.sha256(f"공고\n{body}".encode()).hexdigest()
    return {
        "source": "kofia",
        "external_id": "1",
        "source_url": "https://example.com/1",
        "company": "테스트운용",
        "title": "공고",
        "body_text": body,
        "posted_at": "2026-08-05",
        "deadline_at": None,
        "audience": "unknown",
        "employment_type": None,
        "classification_note": "분류 표현 없음",
        "attachments": [],
        "content_hash": digest,
    }


def test_upsert_preserves_first_seen_and_snapshots_changes(tmp_path) -> None:
    connection = connect(tmp_path / "test.sqlite3")
    assert upsert_posting(connection, make_posting("처음"), "<p>처음</p>") == "created"
    first_seen = connection.execute("SELECT first_seen_at FROM postings").fetchone()[0]

    assert upsert_posting(connection, make_posting("처음"), "<p>처음</p>") == "unchanged"
    assert connection.execute("SELECT first_seen_at FROM postings").fetchone()[0] == first_seen
    assert connection.execute("SELECT COUNT(*) FROM posting_snapshots").fetchone()[0] == 1

    assert upsert_posting(connection, make_posting("수정"), "<p>수정</p>") == "updated"
    assert connection.execute("SELECT COUNT(*) FROM postings").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM posting_snapshots").fetchone()[0] == 2
    connection.close()

