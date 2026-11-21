import sqlite3, re, json, sys
from pathlib import Path
from datetime import date
from collections import Counter
sys.path.insert(0, str(Path('src').resolve()))
from job_archive.fit_model import Posting, deduplicate_postings, classify_quant_subtype, SKILLS
# 원본 DB는 읽기 전용으로 열고 최근 3년의 공고를 동일 기준으로 비교한다.
c = sqlite3.connect('file:data/jobs.sqlite3?mode=ro', uri=True)
c.row_factory = sqlite3.Row
rows = [dict(r) for r in c.execute("select *, coalesce(manual_audience,audience) as target from postings where posted_at >= '2023-09-15' and posted_at <= '2026-09-14'")]
pat = r'퀀트|\bquant(?:itative)?\b|계량\s*운용|알고리즘\s*(?:트레이딩|매매)|시스템\s*트레이딩'
core = [r for r in rows if re.search(pat, r['title']+'\n'+(r['body_text'] or ''), re.I)]
def posts(rs):
    return [Posting(r['id'],r['company'] or '',r['title'],r['body_text'] or '',date.fromisoformat(r['posted_at'][:10]),r['source_url'],r['job_category_1'],r['job_category_2'],r['target'],classify_quant_subtype(r['title'],r['body_text'] or '')) for r in rs]
p = deduplicate_postings(posts(core))
entry = [r for r in p if r.audience in ('intern','entry_level','mixed')]
# 빈도는 공고 전체의 언급률이며 필수요건 또는 채용인원 비율로 해석하지 않는다.
def summarize(ps):
    return {'n':len(ps),'companies':Counter(x.company for x in ps).most_common(15),'company_types':Counter(next(r['company_category'] for r in core if r['id']==x.id) for x in ps),'audience':Counter(x.audience for x in ps),'subtypes':Counter(x.quant_subtype for x in ps),'skills':{s.label:sum(any(re.search(z,x.title+'\n'+x.body_text,re.I) for z in s.patterns) for x in ps) for s in SKILLS},'years':Counter(str(x.posted_at.year) for x in ps)}
result={'recent_all':len(rows),'broad_quant':sum(r['job_category_1']=='quant_data' or r['job_category_2']=='quant_data' for r in rows),'core_raw':len(core),'core':summarize(p),'entry':summarize(entry)}
Path('docs/quant_career_analysis_20260918.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
Path('docs/quant_career_evidence_20260918.txt').write_text('\n\n'.join(f'ID {x.id} | {x.posted_at} | {x.company} | {x.audience} | {x.quant_subtype}\n{x.title}\n{x.source_url}\n{x.body_text}' for x in entry),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
print('RECENT ENTRY')
for x in entry[:30]: print(x.id,x.posted_at,x.company,x.title,x.source_url)
# 회사명·이메일·URL에만 있는 퀀트 문자열을 제거해 검색 오탐을 줄인다.
def relevant_text(r):
    t = r['title']+'\n'+(r['body_text'] or '')
    if r['company']: t=t.replace(r['company'],'')
    t=re.sub(r'https?://\S+|[\w.+-]+@[\w.-]+',' ',t)
    return t
clean = [r for r in core if re.search(pat,relevant_text(r),re.I)]
cp=deduplicate_postings(posts(clean))
result['clean_core']=summarize(cp)
result['clean_entry_candidates']=summarize([x for x in cp if x.audience in ('intern','entry_level','mixed')])
Path('docs/quant_career_analysis_20260918.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('CLEAN',json.dumps(result['clean_core'],ensure_ascii=True))
print('ENTRY',json.dumps(result['clean_entry_candidates'],ensure_ascii=True))
