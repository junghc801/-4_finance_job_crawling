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


@dataclass(frozen=True)
class Classification:
    audience: str
    employment_type: str | None
    note: str


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

