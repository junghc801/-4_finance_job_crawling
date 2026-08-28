from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from functools import lru_cache


TARGET_AUDIENCES = ("intern", "entry_level", "mixed")

QUANT_SUBTYPE_LABELS = {
    "quant_research": "퀀트 리서치",
    "quant_asset_management": "퀀트 운용·자산배분",
    "algorithmic_trading": "알고리즘 트레이딩",
    "risk_modeling": "리스크 모델링",
    "quant_development": "퀀트 개발",
    "financial_data_ai": "금융 데이터·AI",
    "quant_general": "퀀트 일반",
}

QUANT_SUBTYPE_PATTERNS = {
    "quant_research": (r"퀀트\s*(?:리서치|연구)", r"투자전략", r"팩터", r"백테스트"),
    "quant_asset_management": (r"자산배분", r"포트폴리오", r"퀀트\s*운용", r"계량\s*운용"),
    "algorithmic_trading": (r"알고리즘\s*트레이딩", r"자동\s*매매", r"시스템\s*트레이딩", r"트레이더"),
    "risk_modeling": (r"리스크\s*(?:모델|관리|분석)", r"위험\s*관리", r"var\b"),
    "quant_development": (r"평가\s*엔진", r"퀀트\s*개발", r"모델\s*개발", r"데이터\s*엔지니어"),
    "financial_data_ai": (r"금융\s*데이터", r"데이터\s*분석", r"머신\s*러닝", r"\bai\b", r"\bllm\b"),
}


@dataclass(frozen=True)
class SkillDefinition:
    key: str
    label: str
    category: str
    patterns: tuple[str, ...]


SKILLS = (
    SkillDefinition("python", "Python", "programming", (r"\bpython\b", r"파이썬")),
    SkillDefinition("r", "R", "programming", (r"(?<![a-z])r(?![a-z])", r"R\s*언어")),
    SkillDefinition("cpp", "C++", "programming", (r"c\+\+",)),
    SkillDefinition("java", "Java", "programming", (r"\bjava\b",)),
    SkillDefinition("matlab", "MATLAB", "programming", (r"\bmatlab\b",)),
    SkillDefinition("sas", "SAS", "programming", (r"\bsas\b",)),
    SkillDefinition("vba", "VBA", "programming", (r"\bvba\b",)),
    SkillDefinition("sql", "SQL", "query", (r"(?<![a-z])sql(?![a-z])",)),
    SkillDefinition("mysql", "MySQL", "database", (r"\bmysql\b",)),
    SkillDefinition("postgresql", "PostgreSQL", "database", (r"\bpostgres(?:ql)?\b",)),
    SkillDefinition("oracle", "Oracle", "database", (r"\boracle\b", r"오라클")),
    SkillDefinition("pandas", "pandas", "data_ml", (r"\bpandas\b",)),
    SkillDefinition("numpy", "NumPy", "data_ml", (r"\bnumpy\b",)),
    SkillDefinition("scikit_learn", "scikit-learn", "data_ml", (r"scikit[- ]?learn", r"sklearn")),
    SkillDefinition("pytorch", "PyTorch", "data_ml", (r"\bpytorch\b",)),
    SkillDefinition("tensorflow", "TensorFlow", "data_ml", (r"\btensorflow\b",)),
    SkillDefinition("machine_learning", "머신러닝", "data_ml", (r"머신\s*러닝", r"machine\s*learning", r"\bml\b")),
    SkillDefinition("deep_learning", "딥러닝", "data_ml", (r"딥\s*러닝", r"deep\s*learning")),
    SkillDefinition("statistics", "통계", "quantitative", (r"통계(?:학|분석|적)", r"statistics?")),
    SkillDefinition("time_series", "시계열 분석", "quantitative", (r"시계열", r"time\s*series")),
    SkillDefinition("optimization", "최적화", "quantitative", (r"최적화", r"optimization")),
    SkillDefinition("investment_manager", "투자자산운용사", "investment_manager_certificate", (r"투자자산운용사", r"투운사")),
    SkillDefinition("cfa", "CFA", "other_certificate", (r"(?<![a-z])cfa(?![a-z])",)),
    SkillDefinition("frm", "FRM", "other_certificate", (r"(?<![a-z])frm(?![a-z])",)),
    SkillDefinition("financial_analyst", "금융투자분석사", "other_certificate", (r"금융투자분석사",)),
    SkillDefinition("derivatives_advisor", "파생상품 관련 자격증", "other_certificate", (r"파생상품.{0,8}자격증", r"파생상품투자권유자문인력")),
    SkillDefinition("accountant", "회계사", "other_certificate", (r"(?<![a-z])k?icpa(?![a-z])", r"공인회계사")),
    SkillDefinition("other_finance_certificate", "기타 금융 자격증", "other_certificate", (r"금융\s*(?:관련\s*)?자격증", r"금융투자.{0,5}자격")),
    SkillDefinition("excel", "Excel", "tool", (r"\bexcel\b", r"엑셀")),
    SkillDefinition("office", "MS Office", "tool", (r"ms[- ]?office", r"오피스\s*활용", r"컴퓨터\s*활용")),
    SkillDefinition("bloomberg", "Bloomberg", "tool", (r"\bbloomberg\b", r"블룸버그")),
    SkillDefinition("git", "Git", "tool", (r"(?<![a-z])git(?![a-z])",)),
    SkillDefinition("linux", "Linux/Unix", "tool", (r"\blinux\b", r"\bunix\b")),
    SkillDefinition("english", "영어", "language", (r"영어", r"어학.{0,5}우수", r"english")),
    SkillDefinition("bachelor", "학사", "education", (r"(?:4년제\s*)?(?:대학|대학교).{0,8}(?:졸업|재학|예정)", r"학사(?:학위)?\s*이상")),
    SkillDefinition("master", "석사", "education", (r"(?<!분)석사", r"대학원")),
    SkillDefinition("phd", "박사", "education", (r"박사",)),
    SkillDefinition("related_major", "관련 전공", "education", (r"관련\s*(?:학과|전공)", r"(?:금융공학|수학|통계학|경제학|경영학|컴퓨터공학|산업공학).{0,12}전공")),
    SkillDefinition("finance_experience", "금융·퀀트 유관 경험", "experience", (r"(?:금융|자산운용|증권|퀀트|투자).{0,15}(?:경험|경력)", r"유관\s*(?:업무\s*)?(?:경험|경력)")),
    SkillDefinition("finance_project", "금융·데이터 프로젝트", "experience", (r"(?:금융|데이터|퀀트).{0,15}(?:프로젝트|공모전)",)),
)

SKILL_BY_KEY = {skill.key: skill for skill in SKILLS}
OTHER_CERTIFICATE_KEYS = {
    skill.key for skill in SKILLS if skill.category == "other_certificate"
}

REQUIRED_HEADINGS = (
    "자격요건", "지원자격", "응시자격", "자격사항", "필요한 경험", "필요해요",
    "필수요건", "필수 요건", "공통요건",
)
PREFERRED_HEADINGS = (
    "우대사항", "우대 사항", "우대요건", "우대 요건", "더욱 좋아요", "우대자격",
)
DESCRIPTION_HEADINGS = (
    "담당업무", "담당 업무", "주요업무", "주요 업무", "업무내용", "업무 내용",
    "모집부문", "모집 부문", "근무조건", "근무 조건", "전형방법", "전형절차",
    "제출서류", "지원방법", "접수기간", "기타사항", "기타 사항",
)


@dataclass(frozen=True)
class Posting:
    id: int
    company: str
    title: str
    body_text: str
    posted_at: date
    source_url: str
    job_category_1: str
    job_category_2: str | None
    audience: str
    quant_subtype: str = "quant_general"


@dataclass(frozen=True)
class Requirement:
    alternatives: tuple[str, ...]
    kind: str
    evidence: str
    minimum_level: int = 1
    minimum_months: int = 0

    @property
    def label(self) -> str:
        return " 또는 ".join(SKILL_BY_KEY[key].label for key in self.alternatives)


@dataclass(frozen=True)
class ApplicantProfile:
    skill_levels: dict[str, int] = field(default_factory=dict)
    education: str = "none"
    related_major: bool = False
    finance_experience_months: int = 0

    def level_for(self, skill_key: str) -> int:
        if skill_key == "bachelor":
            return int(self.education in {"bachelor", "master", "phd"}) * 3
        if skill_key == "master":
            return int(self.education in {"master", "phd"}) * 3
        if skill_key == "phd":
            return int(self.education == "phd") * 3
        if skill_key == "related_major":
            return int(self.related_major) * 3
        if skill_key == "finance_experience":
            return 3 if self.finance_experience_months else 0
        if skill_key == "other_finance_certificate":
            return 3 if any(
                key != "other_finance_certificate" and self.skill_levels.get(key, 0) > 0
                for key in OTHER_CERTIFICATE_KEYS
            ) else 0
        return max(0, min(3, int(self.skill_levels.get(skill_key, 0))))


@dataclass(frozen=True)
class FitResult:
    posting: Posting
    required_score: float
    preferred_score: float
    total_score: float
    required_count: int
    preferred_count: int
    matched_required: tuple[str, ...]
    matched_preferred: tuple[str, ...]
    missing_required: tuple[str, ...]
    missing_preferred: tuple[str, ...]
    required_not_stated: bool
    extraction_warning: str | None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _years_before(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)


def classify_quant_subtype(title: str, body_text: str) -> str:
    title_text = title.lower()
    body = body_text.lower()
    scores = {
        subtype: sum(4 for pattern in patterns if re.search(pattern, title_text, re.IGNORECASE))
        + sum(1 for pattern in patterns if re.search(pattern, body, re.IGNORECASE))
        for subtype, patterns in QUANT_SUBTYPE_PATTERNS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "quant_general"


def load_model_postings(
    connection: sqlite3.Connection, years: int
) -> tuple[list[Posting], date, date]:
    if years not in {3, 5}:
        raise ValueError("분석 기간은 3년 또는 5년이어야 합니다.")

    placeholders = ",".join("?" for _ in TARGET_AUDIENCES)
    base_conditions = f"""
        (job_category_1 = 'quant_data' OR job_category_2 = 'quant_data')
        AND COALESCE(manual_audience, audience) IN ({placeholders})
    """
    latest_value = connection.execute(
        f"SELECT MAX(posted_at) FROM postings WHERE {base_conditions}",
        TARGET_AUDIENCES,
    ).fetchone()[0]
    latest = _parse_date(latest_value)
    if latest is None:
        return [], date.min, date.min
    cutoff = _years_before(latest, years)

    rows = connection.execute(
        f"""
        SELECT id, COALESCE(company, ''), title, COALESCE(body_text, ''),
               posted_at, source_url, job_category_1, job_category_2,
               COALESCE(manual_audience, audience)
        FROM postings
        WHERE {base_conditions} AND posted_at >= ? AND posted_at <= ?
        ORDER BY posted_at DESC, id DESC
        """,
        (*TARGET_AUDIENCES, cutoff.isoformat(), latest.isoformat()),
    ).fetchall()
    postings = [
        Posting(
            id=int(row[0]),
            company=row[1],
            title=row[2],
            body_text=row[3],
            posted_at=_parse_date(row[4]) or cutoff,
            source_url=row[5],
            job_category_1=row[6],
            job_category_2=row[7],
            audience=row[8],
            quant_subtype=classify_quant_subtype(row[2], row[3]),
        )
        for row in rows
    ]
    return deduplicate_postings(postings), cutoff, latest


def _normalize_company(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def _normalize_title(value: str, company: str) -> str:
    text = value.lower()
    if company:
        text = text.replace(company.lower(), "")
    text = re.sub(r"\[[^]]+]", " ", text)
    text = re.sub(r"20\d{2}[./년-]\s*\d{1,2}(?:[./월-]\s*\d{1,2})?", " ", text)
    text = re.sub(r"\([^)]*(?:마감|연장|채용)[^)]*\)", " ", text)
    text = re.sub(r"\b(?:채용|공고|모집|연장)\b", " ", text)
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def _normalize_body(value: str) -> str:
    text = value.lower()
    text = re.sub(r"[\w.+-]+@[\w.-]+", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"20\d{2}\s*[년./-]\s*\d{1,2}\s*[월./-]\s*\d{1,2}", " ", text)
    text = re.sub(r"\d{2,4}[-.)/]\d{2,4}[-.)/]\d{3,4}", " ", text)
    return re.sub(r"[^0-9a-z가-힣]+", "", text)


def deduplicate_postings(
    postings: list[Posting], *, within_days: int = 90, similarity: float = 0.92
) -> list[Posting]:
    """같은 회사·직무의 90일 이내 동일/유사 재게시만 합친다."""
    groups: dict[tuple[str, str], list[tuple[Posting, str]]] = {}
    kept: list[Posting] = []
    for posting in sorted(postings, key=lambda item: (item.posted_at, item.id), reverse=True):
        key = (
            _normalize_company(posting.company),
            _normalize_title(posting.title, posting.company),
        )
        body = _normalize_body(posting.body_text)
        duplicate = False
        for existing, existing_body in groups.get(key, []):
            if abs((existing.posted_at - posting.posted_at).days) > within_days:
                continue
            if body == existing_body or SequenceMatcher(None, body, existing_body).ratio() >= similarity:
                duplicate = True
                break
        if not duplicate:
            kept.append(posting)
            groups.setdefault(key, []).append((posting, body))
    return kept


def _line_kind(line: str, current: str) -> str:
    lowered = line.lower()
    has_preferred = any(value in lowered for value in PREFERRED_HEADINGS) or "우대" in lowered
    has_required = "필수" in lowered or any(value in lowered for value in REQUIRED_HEADINGS)
    if has_preferred and has_required:
        return "mixed"
    if has_preferred:
        return "preferred"
    if has_required:
        return "required"
    if any(value in lowered for value in DESCRIPTION_HEADINGS):
        return "description"
    return current


def _skill_keys(line: str) -> list[str]:
    matches = []
    for skill in SKILLS:
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in skill.patterns):
            matches.append(skill.key)
    # 구체 자격증과 포괄적 '금융 자격증' 표현이 같은 문장에서 중복되는 것을 방지한다.
    if "other_finance_certificate" in matches and len(OTHER_CERTIFICATE_KEYS.intersection(matches)) > 1:
        matches.remove("other_finance_certificate")
    return matches


def _minimum_level(line: str) -> int:
    if re.search(r"능숙|숙련|고급|실무\s*경험|전문성", line):
        return 3
    if re.search(r"프로젝트|활용\s*경험|개발\s*경험|분석\s*경험", line):
        return 2
    return 1


def _minimum_months(line: str) -> int:
    match = re.search(r"(?:경력\s*)?(\d+)\s*년\s*(?:이상)?", line)
    return int(match.group(1)) * 12 if match else 0


@lru_cache(maxsize=8192)
def extract_requirements(body_text: str) -> tuple[list[Requirement], str | None]:
    requirements: list[Requirement] = []
    current_kind = "description"
    lines = [line.strip(" \t-*·▶□■※") for line in body_text.replace("\r", "").split("\n")]
    for line in lines:
        if not line:
            continue
        current_kind = _line_kind(line, current_kind)
        explicit_kind = _line_kind(line, current_kind)
        if explicit_kind == "mixed":
            explicit_kind = "preferred" if "우대" in line else "required"
        if explicit_kind not in {"required", "preferred"}:
            continue
        keys = _skill_keys(line)
        if not keys:
            continue
        minimum_level = _minimum_level(line)
        minimum_months = _minimum_months(line)
        has_alternative = bool(re.search(r"또는|혹은|중\s*(?:하나|1개)|\bor\b", line, re.IGNORECASE))
        if has_alternative and len(keys) > 1:
            requirements.append(
                Requirement(tuple(dict.fromkeys(keys)), explicit_kind, line, minimum_level, minimum_months)
            )
        else:
            requirements.extend(
                Requirement((key,), explicit_kind, line, minimum_level, minimum_months)
                for key in dict.fromkeys(keys)
            )

    # 같은 스펙이 필수와 우대에 모두 있으면 필수조건을 우선한다.
    required_keys = {
        alternative
        for requirement in requirements
        if requirement.kind == "required"
        for alternative in requirement.alternatives
    }
    unique: dict[tuple[str, tuple[str, ...]], Requirement] = {}
    for requirement in requirements:
        if requirement.kind == "preferred" and set(requirement.alternatives) <= required_keys:
            continue
        key = (requirement.kind, requirement.alternatives)
        unique.setdefault(key, requirement)

    warning = None
    role_markers = re.findall(
        r"(?m)^\s*(?:\(\d+\)|\d+\))\s*[^\n]{2,50}(?:부문|직무|팀)\s*(?:\([^\n]+\))?\s*$",
        body_text,
    )
    if len(role_markers) >= 2:
        warning = "복수 직무가 한 공고에 포함되어 요건이 섞였을 수 있습니다."
    return list(unique.values()), warning


def _requirement_match(requirement: Requirement, profile: ApplicantProfile) -> float:
    matches = []
    for skill_key in requirement.alternatives:
        if skill_key == "finance_experience" and requirement.minimum_months:
            matches.append(min(1.0, profile.finance_experience_months / requirement.minimum_months))
            continue
        level = profile.level_for(skill_key)
        if requirement.minimum_level >= 3:
            matches.append({0: 0.0, 1: 0.25, 2: 0.5, 3: 1.0}[level])
        elif requirement.minimum_level == 2:
            matches.append({0: 0.0, 1: 0.25, 2: 1.0, 3: 1.0}[level])
        else:
            matches.append({0: 0.0, 1: 0.5, 2: 1.0, 3: 1.0}[level])
    return max(matches, default=0.0)


def _score_group(
    requirements: list[Requirement], profile: ApplicantProfile, maximum: float
) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    if not requirements:
        return (maximum if maximum == 100.0 else 0.0), (), ()

    values = [_requirement_match(requirement, profile) for requirement in requirements]
    other_certificate_indices = [
        index
        for index, requirement in enumerate(requirements)
        if set(requirement.alternatives) <= OTHER_CERTIFICATE_KEYS
    ]
    if len(other_certificate_indices) > 3:
        allowed = set(sorted(other_certificate_indices, key=lambda index: values[index], reverse=True)[:3])
        for index in other_certificate_indices:
            if index not in allowed:
                values[index] = 0.0

    score = maximum * sum(values) / len(requirements)
    matched = tuple(
        requirement.label for requirement, value in zip(requirements, values) if value >= 1.0
    )
    missing = tuple(
        requirement.label for requirement, value in zip(requirements, values) if value < 1.0
    )
    return score, matched, missing


def score_posting(posting: Posting, profile: ApplicantProfile) -> FitResult:
    requirements, warning = extract_requirements(posting.body_text)
    required = [item for item in requirements if item.kind == "required"]
    preferred = [item for item in requirements if item.kind == "preferred"]
    required_score, matched_required, missing_required = _score_group(required, profile, 100.0)
    preferred_score, matched_preferred, missing_preferred = _score_group(preferred, profile, 20.0)
    return FitResult(
        posting=posting,
        required_score=round(required_score, 1),
        preferred_score=round(preferred_score, 1),
        total_score=round(required_score + preferred_score, 1),
        required_count=len(required),
        preferred_count=len(preferred),
        matched_required=matched_required,
        matched_preferred=matched_preferred,
        missing_required=missing_required,
        missing_preferred=missing_preferred,
        required_not_stated=not required,
        extraction_warning=warning,
    )


def rank_postings(postings: list[Posting], profile: ApplicantProfile) -> list[FitResult]:
    results = [score_posting(posting, profile) for posting in postings]
    return sorted(
        results,
        key=lambda result: (
            -result.total_score,
            result.required_not_stated,
            -result.posting.posted_at.toordinal(),
            -result.posting.id,
        ),
    )


def marginal_skill_gains(
    postings: list[Posting], profile: ApplicantProfile, limit: int = 10
) -> list[tuple[str, float, int]]:
    baseline = {result.posting.id: result.total_score for result in rank_postings(postings, profile)}
    mentioned = {
        key
        for posting in postings
        for requirement in extract_requirements(posting.body_text)[0]
        for key in requirement.alternatives
        if profile.level_for(key) < 3 and key not in {"bachelor", "master", "phd", "related_major", "finance_experience"}
    }
    gains = []
    for key in mentioned:
        levels = dict(profile.skill_levels)
        levels[key] = 3
        upgraded = ApplicantProfile(
            skill_levels=levels,
            education=profile.education,
            related_major=profile.related_major,
            finance_experience_months=profile.finance_experience_months,
        )
        scores = rank_postings(postings, upgraded)
        changes = [result.total_score - baseline[result.posting.id] for result in scores]
        improved = sum(change > 0 for change in changes)
        gains.append((key, round(sum(changes) / len(changes), 2) if changes else 0.0, improved))
    return sorted(gains, key=lambda item: (-item[1], -item[2], item[0]))[:limit]
