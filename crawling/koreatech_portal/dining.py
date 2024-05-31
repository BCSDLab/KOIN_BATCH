import requests
import config
from datetime import datetime
from bs4 import BeautifulSoup
import redis as redis_library
from login import portal_login

"""
1. redis에 쿠키 저장 [완]
2. 필요한 경우 로그인 요청 후 쿠키 획득 [완]
  - redis에 저장된 쿠키 만료 시 [완]
  - redis에 저장된 쿠키가 없을 시 [완]
3. 응답 획득 [완]
  - eat_date: 오늘 ~ 일주일 후
  - eat_type: breakfast / lunch / dinner
  - restaurant: 한식 / 일품 / 특식-전골/뚝배기 / 능수관 / (2캠인 경우만 고정) 코너1
  - campus: Campus1 / Campus2
4. MySql에 결과 저장
  - 식사시간에만 빠르게 반복하는 로직도 확인해봐야 함
"""


def send_request(login_cookie, eat_date, eat_type, restaurant, campus):
    headers = {"Content-Type": "text/xml; charset=utf-8"}
    cookies = {"__KSMSID__": f"{login_cookie};Domain=koreatech.ac.kr;"}
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
    <Root xmlns="http://www.nexacroplatform.com/platform/dataset">
        <Parameters>
            <Parameter id="method">getList_sp</Parameter>
            <Parameter id="sqlid">NK_COT_MEAL_PLAN.NP_SELECT_11</Parameter>
            <Parameter id="locale">ko</Parameter>
        </Parameters>
        <Dataset id="input1">
            <ColumnInfo>
                <Column id="CAMPUS" type="string" size="4000" />
                <Column id="RESTURANT" type="string" size="4000" />
                <Column id="EAT_DATE" type="string" size="4000" />
                <Column id="EAT_TYPE" type="string" size="4000" />
            </ColumnInfo>
            <Rows>
                <Row>
                    <Col id="EAT_DATE">{eat_date}</Col>
                    <Col id="EAT_TYPE">{eat_type}</Col>
                    <Col id="RESTURANT">{restaurant}</Col>
                    <Col id="CAMPUS">{campus}</Col>
                </Row>
            </Rows>
        </Dataset>
    </Root>""".encode("utf-8")

    response = requests.post(
        "https://kut90.koreatech.ac.kr/nexacroController.do",
        headers=headers,
        cookies=cookies,
        data=body
    )
    # TODO 에러 발생 시 body에 대한 구체적 조치 필요
    if response.status_code != 200:
        print("잘못된 로그인 쿠키 사용")
        return None
    return response


def connect_redis():
    # Redis 클라이언트 생성
    host = config.REDIS_CONFIG['host']
    port = config.REDIS_CONFIG['port']
    db = config.REDIS_CONFIG['db']
    redis = redis_library.StrictRedis(host=host, port=port, db=db)

    # 연결 테스트
    try:
        redis.ping()
        return redis
    except redis_library.ConnectionError:
        raise ConnectionError("레디스 연결 불가")


def get_cookie(today):
    # redis 캐시 조회
    redis = connect_redis()
    login_cookie = redis.get('__KSMSID__')
    if login_cookie:
        login_cookie = login_cookie.decode("utf-8")
        # TODO 오늘 날짜로 자동세팅 조치 필요
        response = send_request(login_cookie, today, "lunch", "한식", "Campus1")
        soup = BeautifulSoup(response.text, 'lxml-xml')
        if soup.find("Parameter", {"id": "ErrorCode"}).text == '0':
            return login_cookie

    # 아우누리 로그인하여 쿠키 취득
    login_cookie = portal_login()['__KSMSID__']
    if login_cookie is None:
        raise ConnectionError("아우누리 로그인 실패")

    # redis 캐시 저장
    redis.set('__KSMSID__', login_cookie)
    return login_cookie


def parse_row(row):
    return {
        'KCAL': row.find("Col", {"id": "KCAL"}).text,
        'EAT_DATE': row.find("Col", {"id": "EAT_DATE"}).text,
        'CAMPUS': row.find("Col", {"id": "CAMPUS"}).text,
        'PRICE': row.find("Col", {"id": "PRICE"}).text,
        'DISH': row.find("Col", {"id": "DISH"}).text.strip(),
        'RESTURANT': row.find("Col", {"id": "RESTURANT"}).text,
        'EAT_TYPE': row.find("Col", {"id": "EAT_TYPE"}).text
    }


def dining_crawling():
    today = datetime.today().strftime("%Y-%m-%d")
    cookie = get_cookie(today)

    eat_date = today
    eat_type = "lunch"
    restaurant = "한식"
    campus = "Campus1"

    response = send_request(cookie, eat_date, eat_type, restaurant, campus)
    soup = BeautifulSoup(response.text, 'lxml-xml')
    rows = soup.find_all('Row')
    data = [parse_row(row) for row in rows]
    print(data)

dining_crawling()
