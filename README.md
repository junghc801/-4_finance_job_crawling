# 금융 채용공고 아카이브

금융투자협회 모바일 채용 게시판의 공고를 개인용 SQLite 데이터베이스에 저장하고,
Streamlit 화면에서 검색하는 프로젝트입니다. 필요하면 SQLite의 전체 데이터를
MySQL로 복사할 수 있습니다.

## 현재 범위

- 금융투자협회 모바일 채용 목록 및 상세 본문 수집
- 동일 공고 중복 방지
- 최초 발견·최근 확인 시각 저장
- 본문이 바뀐 경우에만 수정 스냅샷 저장
- 규칙 기반 신입·인턴·경력 분류
- 키워드·회사·지원 대상별 검색
- SQLite의 공고·수정 이력·수집 실행 기록을 MySQL로 복사

삭제 여부의 자동 판정과 첨부파일 다운로드는 아직 포함되지 않았습니다.

## 설치

PowerShell에서 프로젝트 폴더로 이동한 뒤 실행합니다.

```powershell
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
```

## 수집

먼저 적은 페이지로 시험합니다.

```powershell
& ".\.venv\Scripts\python.exe" -m job_archive.collect --pages 2 --delay 1.5
```

기본 데이터베이스 위치는 `data/jobs.sqlite3`입니다. 수집 대상 사이트의 이용약관과
robots.txt를 확인해야 합니다.

## 검색 화면

```powershell
& ".\.venv\Scripts\python.exe" -m streamlit run src\job_archive\app.py
```

## MySQL로 복사

MySQL 서버와 대상 데이터베이스는 미리 준비되어 있어야 합니다. 최초 한 번 MySQL에서
다음 데이터베이스를 생성합니다.

```sql
CREATE DATABASE finance_jobs
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

PowerShell에서 접속 정보를 환경변수로 지정하고 복사 명령을 실행합니다.

```powershell
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "root"
$env:MYSQL_DATABASE = "finance_jobs"

& ".\.venv\Scripts\python.exe" -m job_archive.export_mysql
```

`MYSQL_PASSWORD`를 설정하지 않으면 실행할 때 비밀번호를 입력받습니다. 환경변수로
지정하려면 다음 명령을 추가합니다. 실제 비밀번호를 저장소 파일에 기록하지 마세요.

```powershell
$env:MYSQL_PASSWORD = "실제 비밀번호"
```

저장소의 `.env.example`에는 필요한 변수 이름만 정리되어 있습니다. 이 프로젝트는
`.env` 파일을 자동으로 읽지 않으므로 값을 PowerShell 환경변수로 설정해야 합니다.

기본 SQLite 경로는 `data/jobs.sqlite3`이며 `--sqlite`로 바꿀 수 있습니다. MySQL에는
`postings`, `posting_snapshots`, `crawl_runs` 테이블이 자동 생성됩니다. 복사 명령은
한 트랜잭션으로 실행되고, 같은 `id`가 있으면 최신 SQLite 값으로 갱신합니다. MySQL에만
존재하는 행은 삭제하지 않습니다.

사용 가능한 전체 옵션은 다음과 같이 확인합니다.

```powershell
& ".\.venv\Scripts\python.exe" -m job_archive.export_mysql --help
```

## 테스트

```powershell
& ".\.venv\Scripts\python.exe" -m pytest
```

MySQL 관련 테스트는 실제 서버에 접속하지 않고 SQL 생성과 배치 복사 동작을 검사합니다.

## 주요 데이터

- `posted_at`: 사이트에 표시된 게시일
- `first_seen_at`: 이 프로그램이 공고를 처음 발견한 시각
- `last_seen_at`: 마지막으로 공고 상세 페이지를 확인한 시각
- `last_changed_at`: 제목 또는 본문의 마지막 변경 감지 시각
- `audience`: 자동 분류 결과
- `manual_audience`: 사용자가 나중에 정정할 수 있는 분류값

## 주요 파일

- `src/job_archive/collect.py`: 금융투자협회 공고 수집
- `src/job_archive/app.py`: Streamlit 검색 화면
- `src/job_archive/export_mysql.py`: SQLite 데이터를 MySQL로 복사
- `sql/schema.sql`: SQLite 테이블 정의
- `tests/test_export_mysql.py`: MySQL 복사 로직 테스트
