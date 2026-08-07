# 금융 채용공고 아카이브

금융투자협회 모바일 채용 게시판의 공고를 개인용 SQLite 데이터베이스에 저장하고,
Streamlit 화면에서 검색하는 최소 프로젝트입니다.

## 현재 범위

- 금융투자협회 모바일 채용 목록 및 상세 본문 수집
- 동일 공고 중복 방지
- 최초 발견·최근 확인 시각 저장
- 본문이 바뀐 경우에만 수정 스냅샷 저장
- 규칙 기반 신입·인턴·경력 분류
- 키워드·회사·지원 대상별 검색

삭제 여부의 자동 판정과 첨부파일 다운로드는 아직 포함되지 않았습니다.

## 설치

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 수집

먼저 적은 페이지로 시험합니다.

```powershell
python -m job_archive.collect --pages 2 --delay 1.5
```

기본 데이터베이스 위치는 `data/jobs.sqlite3`입니다. 수집 대상 사이트의 이용약관과
robots.txt를 확인해야 합니다.

## 검색 화면

```powershell
streamlit run src/job_archive/app.py
```

## 테스트

```powershell
pytest
```

## 주요 데이터

- `posted_at`: 사이트에 표시된 게시일
- `first_seen_at`: 이 프로그램이 공고를 처음 발견한 시각
- `last_seen_at`: 마지막으로 공고 상세 페이지를 확인한 시각
- `last_changed_at`: 제목 또는 본문의 마지막 변경 감지 시각
- `audience`: 자동 분류 결과
- `manual_audience`: 사용자가 나중에 정정할 수 있는 분류값


