from datetime import date
from pathlib import Path

from job_archive.kofia import parse_detail, parse_list


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_list() -> None:
    listings = parse_list((FIXTURES / "kofia_list.html").read_text(encoding="utf-8"))

    assert len(listings) == 2
    assert listings[0].external_id == "41477"
    assert listings[0].posted_at == date(2026, 8, 5)
    assert listings[0].url.startswith("https://m.kofia.or.kr/")


def test_parse_detail() -> None:
    title = "[흥국자산운용] 기관마케팅본부 인턴(신입) 채용공고"
    detail = parse_detail(
        (FIXTURES / "kofia_detail.html").read_text(encoding="utf-8"), title
    )

    assert "채용 연계형 인턴" in detail.body_text
    assert len(detail.attachments) == 1
    assert detail.attachments[0]["url"].endswith("application.docx")

