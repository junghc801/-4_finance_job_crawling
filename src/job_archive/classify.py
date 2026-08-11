import re
from dataclasses import dataclass
from datetime import date


INTERN_PATTERNS = ("인턴", "인턴십", "채용연계형")
ENTRY_PATTERNS = ("신입", "신입사원", "경력 무관", "경력무관")
EXPERIENCED_PATTERNS = (
    "경력직",
    "경력자",
    "경력 필수",
    "대리급",
    "과장급",
    "차장급",
    "부장급",
)

COMPANY_CATEGORY_LABELS = {
    "securities": "증권사",
    "asset_management": "자산운용사",
    "advisory": "투자자문·일임",
    "bank": "은행",
    "insurance": "보험사",
    "trust_real_estate": "신탁·부동산금융",
    "futures_brokerage": "선물·중개",
    "valuation_service": "평가·펀드서비스",
    "fintech": "핀테크",
    "other": "기타",
}

JOB_CATEGORY_LABELS = {
    "quant_data": "퀀트·데이터",
    "research": "리서치",
    "asset_management": "자산운용",
    "trading": "트레이딩",
    "risk": "리스크관리",
    "ib_corporate_finance": "IB·기업금융",
    "sales_marketing": "영업·마케팅",
    "compliance_legal": "준법·법무",
    "operations": "운용지원·백오피스",
    "it": "IT",
    "finance_accounting": "회계·재무",
    "management_support": "경영지원",
    "other": "기타",
}

COMPANY_CATEGORY_PATTERNS = (
    ("securities", r"증권"),
    ("asset_management", r"자산운용|에셋운용|asset\s*management"),
    ("advisory", r"투자자문|투자일임"),
    ("bank", r"은행|뱅크"),
    ("insurance", r"보험|생명|화재"),
    ("trust_real_estate", r"부동산신탁|리츠|reit|캐피탈"),
    ("futures_brokerage", r"선물|자금중개|채권중개"),
    ("valuation_service", r"자산평가|펀드서비스|제로인"),
    ("fintech", r"핀테크|페이|토스"),
)

JOB_CATEGORY_PATTERNS = {
    "quant_data": (
        r"퀀트", r"quant", r"데이터\s*(?:분석|사이언스|엔지니어)",
        r"머신러닝", r"인공지능", r"\bai\b", r"알고리즘\s*(?:트레이딩|매매)",
        r"모델링",
    ),
    "research": (
        r"리서치", r"애널리스트", r"analyst", r"기업분석", r"산업분석",
        r"투자분석", r"크레딧분석",
    ),
    "asset_management": (
        r"펀드매니저", r"포트폴리오", r"운용역", r"운용본부", r"운용팀",
        r"투자운용", r"주식운용", r"채권운용", r"etf\s*운용", r"대체투자",
    ),
    "trading": (
        r"트레이딩", r"trading", r"딜러", r"dealer", r"\bs&t\b",
        r"세일즈앤트레이딩", r"주식파생",
    ),
    "risk": (r"리스크", r"위험관리", r"\brisk\b"),
    "ib_corporate_finance": (
        r"\bib\b", r"기업금융", r"투자금융", r"프로젝트금융", r"\bpf\b",
        r"\becm\b", r"\bdcm\b", r"m&a", r"\bipo\b", r"구조화금융",
    ),
    "sales_marketing": (
        r"영업", r"마케팅", r"세일즈", r"\brm\b", r"고객관리", r"법인고객",
        r"기관고객",
    ),
    "compliance_legal": (
        r"준법", r"컴플라이언스", r"법무", r"\baml\b", r"자금세탁",
        r"내부통제", r"내부감사", r"감사팀", r"감사업무",
    ),
    "operations": (
        r"운용지원", r"업무지원", r"백오피스", r"오퍼레이션", r"결제",
        r"사무관리", r"펀드회계", r"수탁", r"신탁업무",
    ),
    "it": (
        r"\bit\b", r"개발자", r"개발\s*(?:담당|직무|팀|엔지니어)", r"엔지니어",
        r"시스템", r"\bdba\b", r"정보보호", r"보안", r"인프라", r"클라우드",
    ),
    "finance_accounting": (
        r"회계", r"재무", r"세무", r"자금관리", r"결산", r"treasury",
    ),
    "management_support": (
        r"경영지원", r"인사", r"총무", r"비서", r"홍보", r"전략기획",
        r"경영기획",
    ),
}


@dataclass(frozen=True)
class Classification:
    audience: str
    employment_type: str | None
    note: str


@dataclass(frozen=True)
class CategoryClassification:
    company_category: str
    job_category_1: str
    job_category_2: str | None


def classify_posting(title: str, body_text: str) -> Classification:
    text = f"{title}\n{body_text}"
    has_intern = any(word in text for word in INTERN_PATTERNS)
    has_entry = any(word in text for word in ENTRY_PATTERNS)
    has_experienced = any(word in text for word in EXPERIENCED_PATTERNS) or bool(
        re.search(r"경력\s*\d+\s*년\s*이상", text)
    )

    matched = []
    if has_intern:
        matched.append("인턴 표현")
    if has_entry:
        matched.append("신입 표현")
    if has_experienced:
        matched.append("경력 표현")

    if has_intern and (has_entry or has_experienced):
        audience = "mixed"
    elif has_intern:
        audience = "intern"
    elif has_entry and has_experienced:
        audience = "mixed"
    elif has_entry:
        audience = "entry_level"
    elif has_experienced:
        audience = "experienced"
    else:
        audience = "unknown"

    if "계약직" in text:
        employment_type = "contract"
    elif "정규직" in text:
        employment_type = "permanent"
    elif has_intern:
        employment_type = "intern"
    else:
        employment_type = None

    return Classification(audience, employment_type, ", ".join(matched) or "분류 표현 없음")


def classify_company_category(company: str | None, title: str) -> str:
    text = f"{company or ''}\n{title}".lower()
    for category, pattern in COMPANY_CATEGORY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return "other"


def classify_job_categories(
    company: str | None,
    title: str,
    body_text: str,
) -> tuple[str, str | None]:
    title_text = re.sub(r"^\s*\[[^]]+]\s*", "", title).lower()
    body = body_text.lower()
    if company:
        title_text = title_text.replace(company.lower(), "")
        body = body.replace(company.lower(), "")

    scores: dict[str, int] = {}
    for category, patterns in JOB_CATEGORY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, title_text, re.IGNORECASE):
                score += 5
            if re.search(pattern, body, re.IGNORECASE):
                score += 1
        if score:
            scores[category] = score

    ranked = sorted(
        scores,
        key=lambda category: (-scores[category], list(JOB_CATEGORY_PATTERNS).index(category)),
    )
    if not ranked:
        return "other", None
    return ranked[0], ranked[1] if len(ranked) > 1 else None


def classify_categories(
    company: str | None,
    title: str,
    body_text: str,
) -> CategoryClassification:
    job_category_1, job_category_2 = classify_job_categories(company, title, body_text)
    return CategoryClassification(
        company_category=classify_company_category(company, title),
        job_category_1=job_category_1,
        job_category_2=job_category_2,
    )


def extract_deadline(text: str, posted_at: date | None) -> date | None:
    full_dates = re.findall(r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})", text)
    if full_dates:
        year, month, day = full_dates[-1]
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None

    short = re.search(r"(?:~|까지)\s*(\d{1,2})[./월]\s*(\d{1,2})", text)
    if short and posted_at:
        month, day = map(int, short.groups())
        year = posted_at.year + (1 if month < posted_at.month - 6 else 0)
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None
