import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st


DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "jobs.sqlite3"
AUDIENCE_LABELS = {
    "intern": "인턴",
    "entry_level": "신입",
    "mixed": "신입·경력 혼합",
    "experienced": "경력",
    "unknown": "미분류",
}


st.set_page_config(page_title="금융 채용공고 아카이브", layout="wide")
st.title("금융 채용공고 아카이브")

db_path = Path(st.sidebar.text_input("SQLite 경로", str(DEFAULT_DB)))
if not db_path.exists():
    st.info("먼저 수집 명령을 실행해 데이터베이스를 만들어 주세요.")
    st.stop()

with sqlite3.connect(db_path) as connection:
    companies = [
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT company FROM postings WHERE company IS NOT NULL ORDER BY company"
        )
    ]

keyword = st.sidebar.text_input("제목·본문 검색")
selected_companies = st.sidebar.multiselect("회사", companies)
selected_labels = st.sidebar.multiselect(
    "지원 대상", list(AUDIENCE_LABELS.values()), default=["인턴", "신입", "신입·경력 혼합"]
)
only_open = st.sidebar.checkbox("마감일이 지나지 않은 공고만", value=False)

selected_audiences = [
    key for key, label in AUDIENCE_LABELS.items() if label in selected_labels
]
conditions = ["1 = 1"]
params: list[str] = []
if keyword:
    conditions.append("(title LIKE ? OR body_text LIKE ?)")
    params.extend([f"%{keyword}%", f"%{keyword}%"])
if selected_companies:
    conditions.append(f"company IN ({','.join('?' for _ in selected_companies)})")
    params.extend(selected_companies)
if selected_audiences:
    conditions.append(
        f"COALESCE(manual_audience, audience) IN ({','.join('?' for _ in selected_audiences)})"
    )
    params.extend(selected_audiences)
if only_open:
    conditions.append("(deadline_at IS NULL OR deadline_at >= ?)")
    params.append(date.today().isoformat())

query = f"""
    SELECT id, posted_at, deadline_at, company, title,
           COALESCE(manual_audience, audience) AS audience,
           first_seen_at, last_seen_at, source_url, body_text
    FROM postings
    WHERE {' AND '.join(conditions)}
    ORDER BY COALESCE(posted_at, first_seen_at) DESC, id DESC
"""
with sqlite3.connect(db_path) as connection:
    frame = pd.read_sql_query(query, connection, params=params)

if frame.empty:
    st.warning("조건에 맞는 공고가 없습니다.")
    st.stop()

frame["지원 대상"] = frame["audience"].map(AUDIENCE_LABELS).fillna(frame["audience"])
st.caption(f"검색 결과 {len(frame):,}건")
st.dataframe(
    frame[["posted_at", "deadline_at", "company", "title", "지원 대상", "first_seen_at"]],
    use_container_width=True,
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
st.write(f"게시일: {selected.posted_at or '확인 필요'} / 마감일: {selected.deadline_at or '확인 필요'}")
st.link_button("원문 열기", selected.source_url)
st.text(selected.body_text or "본문 없음")

