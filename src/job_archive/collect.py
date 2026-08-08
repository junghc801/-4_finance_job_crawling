import argparse
import hashlib
import re
from pathlib import Path
from tqdm import tqdm
import time

from job_archive.classify import classify_posting, extract_deadline
from job_archive.database import begin_run, connect, finish_run, upsert_posting
from job_archive.kofia import KofiaClient


DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "jobs.sqlite3"


def company_from_title(title: str, body_text: str) -> str | None:
    match = re.search(
            r"([가-힣A-Za-z0-9㈜·&]+(?:증권|은행|투자자문|자산운용|자산평가|준비법인|자금중개|채권중개|투자일임|부동산신탁|선물|펀드서비스|투자자문|파트너스|에셋운용|제로인))",
            title
            )
    #제목에 없으면 본문에서 추출
    if not match:
        match = re.search(r"([가-힣A-Za-z0-9㈜·&]+(?:증권|은행|투자자문|자산운용|자산평가|준비법인|자금중개|채권중개|투자일임|부동산신탁|선물|펀드서비스|투자자문|파트너스|에셋운용|제로인))",
                                    body_text)
    return match.group(1).strip() if match else None



def content_hash(title: str, body_text: str) -> str:
    normalized = "\n".join((title.strip(), body_text.strip()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def collect(pages: int, db_path: Path, delay: float) -> dict[str, int]:
    connection = connect(db_path)
    client = KofiaClient(delay=delay)
    run_id = begin_run(connection, "kofia")
    counts = {"pages": 0, "seen": 0, "created": 0, "updated": 0}

    try:
        for page in tqdm(range(1, pages + 1), desc="수집 중"):
            _, listings = client.get_list(page)
            counts["pages"] += 1
            if not listings:
                break

            for listing in listings:
                raw_html, detail = client.get_detail(listing)
                classification = classify_posting(listing.title, detail.body_text)
                deadline = extract_deadline(detail.body_text, listing.posted_at)
                posting = {
                    "source": "kofia",
                    "external_id": listing.external_id,
                    "source_url": listing.url,
                    "company": company_from_title(listing.title, detail.body_text),
                    "title": listing.title,
                    "body_text": detail.body_text,
                    "posted_at": listing.posted_at.isoformat() if listing.posted_at else None,
                    "deadline_at": deadline.isoformat() if deadline else None,
                    "audience": classification.audience,
                    "employment_type": classification.employment_type,
                    "classification_note": classification.note,
                    "attachments": detail.attachments,
                    "content_hash": content_hash(listing.title, detail.body_text),
                }
                result = upsert_posting(connection, posting, raw_html)
                counts["seen"] += 1
                if result in counts:
                    counts[result] += 1

        finish_run(
            connection,
            run_id,
            "success",
            pages_fetched=counts["pages"],
            postings_seen=counts["seen"],
            postings_created=counts["created"],
            postings_updated=counts["updated"],
        )
        return counts
    except Exception as error:
        finish_run(
            connection,
            run_id,
            "failed",
            pages_fetched=counts["pages"],
            postings_seen=counts["seen"],
            postings_created=counts["created"],
            postings_updated=counts["updated"],
            error_message=str(error),
        )
        raise
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="금융투자협회 채용공고 수집")
    parser.add_argument("--pages", type=int, default=2, help="수집할 최신 목록 페이지 수")
    parser.add_argument("--delay", type=float, default=0.8, help="HTTP 요청 사이 대기 초")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    args = parser.parse_args()
    if args.pages < 1:
        parser.error("--pages는 1 이상이어야 합니다.")
    if args.delay < 0:
        parser.error("--delay는 0 이상이어야 합니다.")

    counts = collect(args.pages, args.db, args.delay)
    print(
        f"완료: {counts['pages']}페이지, {counts['seen']}개 확인, "
        f"{counts['created']}개 신규, {counts['updated']}개 수정"
    )


if __name__ == "__main__":
    main()

