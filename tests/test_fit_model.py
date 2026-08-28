import sqlite3
from datetime import date

import pytest

from job_archive.fit_model import (
    ApplicantProfile,
    Posting,
    classify_quant_subtype,
    deduplicate_postings,
    extract_requirements,
    load_model_postings,
    score_posting,
)


def posting(
    body: str,
    *,
    posting_id: int = 1,
    posted_at: date = date(2026, 8, 1),
    title: str = "퀀트 연구원 채용",
) -> Posting:
    return Posting(
        id=posting_id,
        company="테스트자산운용",
        title=title,
        body_text=body,
        posted_at=posted_at,
        source_url="https://example.com",
        job_category_1="quant_data",
        job_category_2=None,
        audience="entry_level",
    )


def test_extracts_required_preferred_and_ignores_duties() -> None:
    requirements, warning = extract_requirements(
        """담당업무
- Python을 활용한 데이터 분석
자격요건
- 학사 이상
- Python 또는 R 활용 가능자
우대사항
- 투자자산운용사 보유자
- SQL 프로젝트 경험
"""
    )

    assert warning is None
    values = {(item.kind, item.alternatives) for item in requirements}
    assert ("required", ("bachelor",)) in values
    assert ("required", ("python", "r")) in values
    assert ("preferred", ("investment_manager",)) in values
    assert ("preferred", ("sql",)) in values
    assert len(requirements) == 4


def test_combined_requirements_heading_defaults_to_required_until_preferred_line() -> None:
    requirements, _ = extract_requirements(
        """자격요건 및 우대사항
- Python 활용 가능자
- 투자자산운용사 소지자 우대
"""
    )

    assert [(item.kind, item.alternatives) for item in requirements] == [
        ("required", ("python",)),
        ("preferred", ("investment_manager",)),
    ]


def test_score_uses_100_required_plus_20_preferred() -> None:
    item = posting(
        """자격요건
- Python 활용 가능자
- SQL 활용 가능자
우대사항
- 투자자산운용사 보유자
- CFA 보유자
"""
    )
    profile = ApplicantProfile(
        skill_levels={"python": 2, "investment_manager": 3}
    )

    result = score_posting(item, profile)

    assert result.required_score == 50.0
    assert result.preferred_score == 10.0
    assert result.total_score == 60.0
    assert result.missing_required == ("SQL",)


def test_missing_required_section_gets_100_and_no_preferred_gets_zero() -> None:
    result = score_posting(posting("담당업무\n- Python 데이터 분석"), ApplicantProfile())

    assert result.required_score == 100.0
    assert result.preferred_score == 0.0
    assert result.total_score == 100.0
    assert result.required_not_stated is True


def test_advanced_requirement_uses_partial_skill_levels() -> None:
    item = posting("자격요건\n- Python 실무 경험 필수")

    assert score_posting(item, ApplicantProfile({"python": 1})).required_score == 25.0
    assert score_posting(item, ApplicantProfile({"python": 2})).required_score == 50.0
    assert score_posting(item, ApplicantProfile({"python": 3})).required_score == 100.0


def test_other_certificate_credit_is_capped_at_three() -> None:
    item = posting(
        """우대사항
- CFA 보유자
- FRM 보유자
- 금융투자분석사 보유자
- 파생상품 관련 자격증 보유자
"""
    )
    profile = ApplicantProfile(
        {"cfa": 3, "frm": 3, "financial_analyst": 3, "derivatives_advisor": 3}
    )

    result = score_posting(item, profile)

    assert result.preferred_score == 15.0


def test_investment_manager_does_not_satisfy_other_certificate_group() -> None:
    item = posting("우대사항\n- 금융 관련 자격증 보유자")

    investment_manager_only = score_posting(
        item, ApplicantProfile({"investment_manager": 3})
    )
    cfa = score_posting(item, ApplicantProfile({"cfa": 3}))

    assert investment_manager_only.preferred_score == 0.0
    assert cfa.preferred_score == 20.0


def test_deduplicate_only_near_reposts_within_90_days() -> None:
    body = "자격요건\nPython 활용 가능자\n우대사항\n투자자산운용사"
    items = [
        posting(body, posting_id=1, posted_at=date(2026, 1, 1)),
        posting(body + "\n마감 2026년 2월 1일", posting_id=2, posted_at=date(2026, 1, 20)),
        posting(body, posting_id=3, posted_at=date(2025, 1, 1)),
        posting(body, posting_id=4, posted_at=date(2026, 1, 20), title="리스크 퀀트 채용"),
    ]

    result = deduplicate_postings(items)

    assert {item.id for item in result} == {2, 3, 4}


def test_load_model_postings_uses_latest_target_date_for_windows() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """CREATE TABLE postings (
            id INTEGER, company TEXT, title TEXT, body_text TEXT, posted_at TEXT,
            source_url TEXT, job_category_1 TEXT, job_category_2 TEXT,
            audience TEXT, manual_audience TEXT
        )"""
    )
    rows = [
        (1, "A", "최신", "", "2026-08-01", "u", "quant_data", None, "entry_level", None),
        (2, "B", "3년 이내", "", "2023-08-01", "u", "quant_data", None, "intern", None),
        (3, "C", "3년 밖", "", "2023-07-31", "u", "quant_data", None, "mixed", None),
        (4, "D", "경력", "", "2026-07-01", "u", "quant_data", None, "experienced", None),
    ]
    connection.executemany("INSERT INTO postings VALUES (?,?,?,?,?,?,?,?,?,?)", rows)

    results, cutoff, latest = load_model_postings(connection, 3)

    assert cutoff == date(2023, 8, 1)
    assert latest == date(2026, 8, 1)
    assert {item.id for item in results} == {1, 2}


def test_only_three_or_five_year_models_are_allowed() -> None:
    connection = sqlite3.connect(":memory:")
    with pytest.raises(ValueError):
        load_model_postings(connection, 4)


def test_quant_subtype_uses_title_more_than_body() -> None:
    assert classify_quant_subtype(
        "알고리즘 트레이딩 담당자", "금융 데이터 분석과 리스크 관리"
    ) == "algorithmic_trading"
