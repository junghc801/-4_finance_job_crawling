from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from job_archive.classify import COMPANY_CATEGORY_LABELS, JOB_CATEGORY_LABELS
from job_archive.database import connect
from job_archive.fit_model import (
    OTHER_CERTIFICATE_KEYS,
    QUANT_SUBTYPE_LABELS,
    SKILL_BY_KEY,
    SKILLS,
    ApplicantProfile,
    load_model_postings,
    marginal_skill_gains,
    rank_postings,
)


DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "jobs.sqlite3"
AUDIENCE_LABELS = {
    "intern": "인턴",
    "entry_level": "신입",
    "mixed": "신입·경력 혼합",
    "experienced": "경력",
    "unknown": "미분류",
}

PROFILE_SKILLS = [
    skill
    for skill in SKILLS
    if skill.category not in {"education", "investment_manager_certificate", "other_certificate"}
    and skill.key != "finance_experience"
]
CERTIFICATE_SKILLS = [
    skill
    for skill in SKILLS
    if skill.key == "investment_manager"
    or (skill.key in OTHER_CERTIFICATE_KEYS and skill.key != "other_finance_certificate")
]
EDUCATION_VALUES = {
    "해당 없음": "none",
    "학사·재학·졸업예정": "bachelor",
    "석사": "master",
    "박사": "phd",
}


@st.cache_data(show_spinner=False)
def cached_model_postings(
    db_path_value: str, years: int, db_modified_ns: int
):
    del db_modified_ns
    with connect(Path(db_path_value)) as connection:
        return load_model_postings(connection, years)


def _profile_from_form() -> ApplicantProfile:
    skill_options = {skill.label: skill.key for skill in PROFILE_SKILLS}
    certificate_options = {skill.label: skill.key for skill in CERTIFICATE_SKILLS}

    st.write("기술 숙련도")
    st.caption("같은 기술을 여러 수준에 선택하면 가장 높은 수준을 적용합니다.")
    basic = st.multiselect("수업·기초 학습", skill_options, key="fit_basic")
    project = st.multiselect("개인·팀 프로젝트 사용", skill_options, key="fit_project")
    practical = st.multiselect("인턴·실무·연구 사용", skill_options, key="fit_practical")
    certificates = st.multiselect(
        "보유 자격증",
        certificate_options,
        help="투자자산운용사는 별도 그룹이며, 나머지 금융 자격증은 최대 3개까지 점수에 반영됩니다.",
    )
    education_label = st.selectbox("학력", EDUCATION_VALUES)
    related_major = st.checkbox("금융·경제·수학·통계·컴퓨터공학 등 관련 전공")
    experience_months = int(
        st.number_input("금융·퀀트 유관 경험(개월)", min_value=0, max_value=600, step=1)
    )

    levels: dict[str, int] = {}
    for level, selected in ((1, basic), (2, project), (3, practical)):
        for label in selected:
            key = skill_options[label]
            levels[key] = max(level, levels.get(key, 0))
    for label in certificates:
        levels[certificate_options[label]] = 3
    return ApplicantProfile(
        skill_levels=levels,
        education=EDUCATION_VALUES[education_label],
        related_major=related_major,
        finance_experience_months=experience_months,
    )


def _render_period_results(db_path: Path, years: int, profile: ApplicantProfile) -> None:
    postings, cutoff, latest = cached_model_postings(
        str(db_path), years, db_path.stat().st_mtime_ns
    )
    if not postings:
        st.warning("분석할 퀀트 공고가 없습니다.")
        return

    with st.spinner(f"최근 {years}년 공고 적합도를 계산하고 있습니다."):
        results = rank_postings(postings, profile)
        gains = marginal_skill_gains(postings, profile)

    no_required = sum(result.required_not_stated for result in results)
    warnings = sum(bool(result.extraction_warning) for result in results)
    metric_columns = st.columns(4)
    metric_columns[0].metric("중복 제거 후 공고", f"{len(results):,}건")
    metric_columns[1].metric("분석 기간", f"{cutoff}~{latest}")
    metric_columns[2].metric("필수조건 미기재", f"{no_required:,}건")
    metric_columns[3].metric("복수 직무 경고", f"{warnings:,}건")

    subtype_counts = pd.Series(
        [QUANT_SUBTYPE_LABELS[result.posting.quant_subtype] for result in results]
    ).value_counts()
    st.caption(
        "직무 구성: "
        + ", ".join(f"{label} {count}건" for label, count in subtype_counts.items())
    )

    st.subheader("스펙 추가 효과")
    if gains:
        gain_frame = pd.DataFrame(
            [
                {
                    "스펙": SKILL_BY_KEY[key].label,
                    "전체 공고 평균 점수 증가": average_gain,
                    "점수가 상승하는 공고": improved,
                }
                for key, average_gain, improved in gains
            ]
        )
        st.dataframe(gain_frame, width="stretch", hide_index=True)
    else:
        st.caption("추가 효과를 계산할 미보유 스펙이 없습니다.")

    st.subheader("공고별 적합도")
    display = pd.DataFrame(
        [
            {
                "ID": result.posting.id,
                "총점": result.total_score,
                "필수": result.required_score,
                "우대": result.preferred_score,
                "필수 요건 수": result.required_count,
                "우대 요건 수": result.preferred_count,
                "필수 미기재": "예" if result.required_not_stated else "",
                "직무 유형": QUANT_SUBTYPE_LABELS[result.posting.quant_subtype],
                "게시일": result.posting.posted_at,
                "회사": result.posting.company,
                "공고": result.posting.title,
                "원문": result.posting.source_url,
            }
            for result in results
        ]
    )
    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={"원문": st.column_config.LinkColumn("원문")},
    )
    st.download_button(
        f"최근 {years}년 적합도 CSV 저장",
        display.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"quant_job_fit_{years}y.csv",
        mime="text/csv",
        key=f"download_fit_{years}",
    )

    choices = {
        f"{result.posting.id} | {result.total_score:.1f}점 | "
        f"{result.posting.company} | {result.posting.title}": result
        for result in results
    }
    selected = choices[
        st.selectbox("적합도 상세", choices, key=f"fit_detail_{years}")
    ]
    st.write(
        f"필수 {selected.required_score:.1f}/100 + "
        f"우대 {selected.preferred_score:.1f}/20 = **{selected.total_score:.1f}/120점**"
    )
    if selected.required_not_stated:
        st.warning("필수조건이 명시되지 않아 필수점수를 100점으로 계산했습니다.")
    if selected.extraction_warning:
        st.warning(selected.extraction_warning)
    details = st.columns(2)
    with details[0]:
        st.write("충족한 필수조건", ", ".join(selected.matched_required) or "없음")
        st.write("충족한 우대조건", ", ".join(selected.matched_preferred) or "없음")
    with details[1]:
        st.write("부족한 필수조건", ", ".join(selected.missing_required) or "없음")
        st.write("부족한 우대조건", ", ".join(selected.missing_preferred) or "없음")
    st.link_button("선택한 공고 원문 열기", selected.posting.source_url)


def render_fit_model(db_path: Path) -> None:
    st.header("퀀트 채용공고 적합도 모델")
    st.info(
        "점수는 추정치입니다. 서류 합격 확률 예측에 도움이 될 수 있으나, 이를 정확히 대변하지 않습니다."
        " 공고에 명시된 필수조건은 최대 100점, "
        "우대조건은 보너스 최대 20점으로 계산합니다."
    )
    with st.form("applicant_profile"):
        profile = _profile_from_form()
        submitted = st.form_submit_button("3년·5년 적합도 계산", type="primary")
    if submitted:
        st.session_state["fit_profile"] = profile
    if "fit_profile" not in st.session_state:
        st.caption("보유 스펙을 입력한 뒤 계산 버튼을 눌러 주세요.")
        return

    profile = st.session_state["fit_profile"]
    tab_3y, tab_5y = st.tabs(["최근 3년", "최근 5년"])
    with tab_3y:
        _render_period_results(db_path, 3, profile)
    with tab_5y:
        _render_period_results(db_path, 5, profile)


st.set_page_config(page_title="금융 채용공고 아카이브", layout="wide")
st.title("금융 채용공고 아카이브")

db_path = Path(st.sidebar.text_input("SQLite 경로", str(DEFAULT_DB)))
if not db_path.exists():
    st.info("먼저 수집 명령을 실행해 데이터베이스를 만들어 주세요.")
    st.stop()

page = st.sidebar.radio("화면", ["공고 검색", "퀀트 적합도 모델"])
if page == "퀀트 적합도 모델":
    render_fit_model(db_path)
    st.stop()

with connect(db_path) as connection:
    companies = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT company FROM postings WHERE company IS NOT NULL ORDER BY company"
        )
    ]

keyword = st.sidebar.text_input("제목·본문 검색")
selected_companies = st.sidebar.multiselect("회사", companies)
selected_company_category_labels = st.sidebar.multiselect(
    "회사 종류", list(COMPANY_CATEGORY_LABELS.values())
)
selected_job_category_labels = st.sidebar.multiselect(
    "직무 종류", list(JOB_CATEGORY_LABELS.values())
)
selected_labels = st.sidebar.multiselect(
    "지원 대상", list(AUDIENCE_LABELS.values()), default=["인턴", "신입", "신입·경력 혼합"]
)
only_open = st.sidebar.checkbox("마감일이 지나지 않은 공고만", value=False)

selected_audiences = [
    key for key, label in AUDIENCE_LABELS.items() if label in selected_labels
]
selected_company_categories = [
    key
    for key, label in COMPANY_CATEGORY_LABELS.items()
    if label in selected_company_category_labels
]
selected_job_categories = [
    key
    for key, label in JOB_CATEGORY_LABELS.items()
    if label in selected_job_category_labels
]
conditions = ["1 = 1"]
params: list[str] = []
if keyword:
    conditions.append("(title LIKE ? OR body_text LIKE ?)")
    params.extend([f"%{keyword}%", f"%{keyword}%"])
if selected_companies:
    conditions.append(f"company IN ({','.join('?' for _ in selected_companies)})")
    params.extend(selected_companies)
if selected_company_categories:
    conditions.append(
        f"company_category IN ({','.join('?' for _ in selected_company_categories)})"
    )
    params.extend(selected_company_categories)
if selected_job_categories:
    placeholders = ",".join("?" for _ in selected_job_categories)
    conditions.append(
        f"(job_category_1 IN ({placeholders}) OR job_category_2 IN ({placeholders}))"
    )
    params.extend(selected_job_categories)
    params.extend(selected_job_categories)
if selected_audiences:
    conditions.append(
        f"COALESCE(manual_audience, audience) IN ({','.join('?' for _ in selected_audiences)})"
    )
    params.extend(selected_audiences)
if only_open:
    conditions.append("(deadline_at IS NULL OR deadline_at >= ?)")
    params.append(date.today().isoformat())

query = f"""
    SELECT id, posted_at, deadline_at, company, company_category, title,
           job_category_1, job_category_2,
           COALESCE(manual_audience, audience) AS audience,
           first_seen_at, last_seen_at, source_url, body_text
    FROM postings
    WHERE {' AND '.join(conditions)}
    ORDER BY COALESCE(posted_at, first_seen_at) DESC, id DESC
"""
with connect(db_path) as connection:
    frame = pd.read_sql_query(query, connection, params=params)

if frame.empty:
    st.warning("조건에 맞는 공고가 없습니다.")
    st.stop()

frame["지원 대상"] = frame["audience"].map(AUDIENCE_LABELS).fillna(frame["audience"])
frame["회사 종류"] = (
    frame["company_category"]
    .map(COMPANY_CATEGORY_LABELS)
    .fillna(frame["company_category"])
)
frame["직무 종류 1"] = (
    frame["job_category_1"].map(JOB_CATEGORY_LABELS).fillna(frame["job_category_1"])
)
frame["직무 종류 2"] = (
    frame["job_category_2"].map(JOB_CATEGORY_LABELS).fillna(frame["job_category_2"])
)
st.caption(f"검색 결과 {len(frame):,}건")
st.dataframe(
    frame[[
        "posted_at", "deadline_at", "company", "회사 종류", "title",
        "직무 종류 1", "직무 종류 2", "지원 대상", "first_seen_at",
    ]],
    width="stretch",
    hide_index=True,
)
st.download_button(
    "검색 결과 CSV 저장",
    frame.drop(columns=["body_text"]).to_csv(index=False).encode("utf-8-sig"),
    file_name="finance_job_search.csv",
    mime="text/csv",
)

options = {f"{row.id} | {row.company or ''} | {row.title}": row for row in frame.itertuples()}
selected = options[st.selectbox("상세 공고", options.keys())]
st.subheader(selected.title)
st.write(f"회사: {selected.company or '확인 필요'}")
st.write(
    f"회사 종류: {COMPANY_CATEGORY_LABELS.get(selected.company_category, selected.company_category)}"
)
job_labels = [
    JOB_CATEGORY_LABELS.get(category, category)
    for category in (selected.job_category_1, selected.job_category_2)
    if pd.notna(category) and str(category).strip()
]
st.write(f"직무 종류: {', '.join(job_labels)}")
st.write(f"게시일: {selected.posted_at or '확인 필요'} / 마감일: {selected.deadline_at or '확인 필요'}")
st.link_button("원문 열기", selected.source_url)
st.text(selected.body_text or "본문 없음")
