import re

def company_from_title(title: str, body_text: str) -> str | None:
    match = re.search(
            r"([가-힣A-Za-z0-9㈜·&]+(?:증권|은행|투자자문|자산운용|자산평가|준비법인|자금중개|채권중개|투자일임|부동산신탁|선물|펀드서비스|투자자문|파트너스|에셋운용|제로인))",
            title
            )
    if not match:
        match = re.search(r"([가-힣A-Za-z0-9㈜·&]+(?:증권|은행|투자자문|자산운용|자산평가|준비법인|자금중개|채권중개|투자일임|부동산신탁|선물|펀드서비스|투자자문|파트너스|에셋운용|제로인))",
                                    body_text)
    return match.group(1).strip()



test1 = '증권업무부 (Settlement Processing) 신입 및 경력직원 채용'
test1_body = "* 회사명: 씨지에스 인터내셔널증권 홍콩 한국지점 * 영문명:CGS International Securities Hong Kong Limited, Korea Branch" \
"* 주소: 서울시 종로구 새문안로 82, 에스타워 15층"



test2 = '케이핀자산운용 운용지원 경력직 채용'
test2_body = ''


print('test1: ')
print(company_from_title(test1, test1_body))
print('\n')
print('test2: ')
print(company_from_title(test2, test2_body))
