from datetime import date

from job_archive.classify import (
    classify_categories,
    classify_company_category,
    classify_job_categories,
    classify_posting,
    extract_deadline,
)


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


def test_company_category() -> None:
    assert classify_company_category("미래에셋자산운용", "채용") == "asset_management"
    assert classify_company_category("한국투자증권", "채용") == "securities"


def test_job_categories_are_limited_to_two() -> None:
    result = classify_categories(
        "테스트자산운용",
        "[테스트자산운용] 퀀트 리서치 인턴",
        "포트폴리오 운용과 데이터 분석 업무",
    )

    assert result.company_category == "asset_management"
    assert result.job_category_1 == "quant_data"
    assert result.job_category_2 == "research"


def test_single_job_category_has_empty_second_slot() -> None:
    first, second = classify_job_categories(
        "테스트증권", "[테스트증권] 준법감시인 채용", "내부통제 업무"
    )

    assert first == "compliance_legal"
    assert second is None
