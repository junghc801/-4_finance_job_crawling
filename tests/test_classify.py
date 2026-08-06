from datetime import date

from job_archive.classify import classify_posting, extract_deadline


def test_intern_and_entry_is_mixed() -> None:
    result = classify_posting("인턴(신입) 채용", "채용 연계형 인턴")
    assert result.audience == "mixed"
    assert result.employment_type == "intern"


def test_experienced_posting() -> None:
    result = classify_posting("운용역 채용", "관련 경력 3년 이상")
    assert result.audience == "experienced"


def test_extracts_last_full_date_as_deadline() -> None:
    result = extract_deadline("접수 기간: 2026.08.05 ~ 2026.08.14", date(2026, 8, 5))
    assert result == date(2026, 8, 14)

