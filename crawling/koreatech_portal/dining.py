import re
import json
import time

import pymysql
import requests
import config
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import redis as redis_library
from login import portal_login

"""
동작 과정
1. 아우누리 식단을 크롤링한다.
    1. redis에 저장된 쿠키가 있으면 사용한다.
    2. redis에 저장된 쿠키가 없으면 아우누리에 로그인하여 쿠키를 저장한다.
2. 크롤링한 식단 정보를 DB에 저장한다.
    1. DB에 저장된 식단 정보와 비교하여 변경된 식단이 있으면 업데이트한다.
    2. 이 때는 식단이 변경되어도 is_changed를 업데이트하지 않는다.
3. 현재 시간이 식사 시간인지 확인한다.
4. 식사시간이 아니면 종료된다.
5. 식사시간이면 현재 식사시간 메뉴를 크롤링한다.
6. 이전에 크롤링했던 메뉴 정보와 새로 크롤링한 메뉴 정보를 비교한다.
7. 변경된 메뉴가 있으면 DB를 업데이트한다.
    1. 이 때는 is_changed를 현재 시간으로 업데이트한다.
8. 식사시간이 끝날 때까지 5번부터 반복한다.




DB 커넥션 open/close 위치 바꾸기
"""

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
4. MySql에 결과 저장 [완]
  - 변경 여부 확인
  - 식사시간에만 빠르게 반복하는 로직도 확인해봐야 함
"""


class MenuEntity:
    def __init__(self, date, dining_time, place, price_card, price_cash, kcal, menu):
        self.date = date
        self.dining_time = dining_time
        self.place = place
        self.price_card = price_card if price_card is not None else 'NULL'
        self.price_cash = price_cash if price_cash is not None else 'NULL'
        self.kcal = kcal if kcal is not None else 'NULL'
        self.menu = menu

    def __str__(self):
        return '%s, %s, %s, %s, %s, %s' % (
            self.dining_time, self.place, self.price_card, self.price_cash, self.kcal, self.menu
        )

    def __repr__(self):
        return '%s, %s, %s, %s, %s, %s' % (
            self.dining_time, self.place, self.price_card, self.price_cash, self.kcal, self.menu
        )

    def __eq__(self, other):
        if isinstance(other, MenuEntity):
            return self.date == other.date and \
                self.dining_time == other.dining_time and \
                self.place == other.place and \
                self.price_card == other.price_card and \
                self.price_cash == other.price_cash and \
                self.kcal == other.kcal and \
                self.menu == other.menu

        return False


def print_flush(target):
    print(target, flush=True)


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

    soup = BeautifulSoup(response.text, 'lxml-xml')
    if soup.find("Parameter", {"id": "ErrorCode"}).text == '0':
        return login_cookie

    # 잘못된 쿠키 사용 예외 던지기
    raise ConnectionError("잘못된 쿠키 사용")


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


def connect_to_database():
    return pymysql.connect(
        host=config.MYSQL_CONFIG['host'],
        port=config.MYSQL_CONFIG['port'],
        user=config.MYSQL_CONFIG['user'],
        password=config.MYSQL_CONFIG['password'],
        db=config.MYSQL_CONFIG['db'],
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_cookie():
    # redis 캐시 조회
    redis = connect_redis()
    login_cookie = redis.get('__KSMSID__')
    if login_cookie:
        login_cookie = login_cookie.decode("utf-8")
        try:
            send_request(login_cookie, datetime.today().strftime("%Y-%m-%d"), "lunch", "한식", "Campus1")
            return login_cookie
        except ConnectionError:
            pass

    # 아우누리 로그인하여 쿠키 취득
    login_cookie = portal_login()['__KSMSID__']
    redis.set('__KSMSID__', login_cookie)
    return login_cookie


def parse_row(row):
    def clean_text(text):
        # '\t', '\n', '\r' 제거
        text = re.sub(r'[\t\n\r]', ' ', text)
        # 다중 공백 제거
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extract_kcal(kcal_text):
        # 'kcal' 제거하고 숫자만 반환
        match = re.search(r'\d+', kcal_text)
        if match:
            return int(match.group())
        return None

    def parse_dish(dish_text):
        # '\t', '\n', '\r' 제거 및 다중 공백 제거
        dish_text = clean_text(dish_text)
        # 마지막 칼로리 정보 및 가격 정보 제거
        dish_text = re.sub(r'\d+ kcal.*', '', dish_text)
        # 각 메뉴를 리스트로 변환
        dishes = [dish.strip() for dish in dish_text.split(' ') if dish]
        return dishes

    def parse_price(price_text):
        # 쉼표와 공백 제거 후 가격 추출
        prices = re.findall(r'\d+', price_text.replace(',', ''))
        # 가격이 두 개 이상일 경우 첫 번째와 두 번째 값을 반환
        if len(prices) >= 2:
            return int(prices[0]), int(prices[1])
        else:
            return None, None

    def parse_place(place_description):
        places = {"한식": "A코너", "일품": "B코너", "특식-전골/뚝배기": "C코너", "능수관": "능수관", "1코너": "1코너"}
        for key in places.keys():
            if key in place_description:
                return places[key]
        raise ValueError("존재하지 않는 코너명")

    try:
        price_card, price_cash = parse_price(row.find("Col", {"id": "PRICE"}).text)
        place = clean_text(row.find("Col", {"id": "RESTURANT"}).text)
        place = parse_place(place)
        campus = clean_text(row.find("Col", {"id": "CAMPUS"}).text)
        if campus == "Campus2":
            place = "2캠퍼스"

        return {
            'kcal': extract_kcal(row.find("Col", {"id": "KCAL"}).text),
            'date': clean_text(row.find("Col", {"id": "EAT_DATE"}).text),
            'campus': campus,
            'price_card': price_card,
            'price_cash': price_cash,
            'menu': parse_dish(row.find("Col", {"id": "DISH"}).text),
            'place': place,
            'dining_time': clean_text(row.find("Col", {"id": "EAT_TYPE"}).text)
        }
    except:
        return None


def check_meal_time():
    def to_minute(hour):
        return hour * 60

    # 분 단위로 변환하여 계산
    now = datetime.now()
    minutes = to_minute(now.hour) + now.minute

    # 조식 08:00~09:30
    if to_minute(8) <= minutes <= to_minute(9) + 30:
        return "BREAKFAST"

    # 중식 11:30~13:30
    if to_minute(1) + 30 <= minutes <= to_minute(13) + 30:
        return "LUNCH"

    # 석식 17:30~18:30
    if to_minute(17) + 30 <= minutes <= to_minute(18) + 30:
        return "DINNER"

    return ''


def update_db(menus, is_changed=None):
    connection = None
    try:
        connection = connect_to_database()
        cur = connection.cursor()

        for menu in menus:
            print_flush("updating to DB..\n%s %s %s" % (menu.date, menu.dining_time, menu.place))
            try:
                # INT는 %s, VARCHAR은 '%s'로 표기 (INT에 NULL 넣기 위함)
                sql = """
                INSERT INTO koin.dining_menus(date, type, place, price_card, price_cash, kcal, menu, is_changed)
                VALUES ('%s', '%s', '%s', %s, %s, %s, '%s', NULL)
                ON DUPLICATE KEY UPDATE price_card = %s, price_cash = %s, kcal = %s, menu = '%s', is_changed = %s
                """

                changed = is_changed.strftime('"%Y-%m-%d %H:%M:%S"') if is_changed else "NULL"

                values = (
                    menu.date, menu.dining_time, menu.place, menu.price_card, menu.price_cash, menu.kcal, menu.menu,
                    menu.price_card, menu.price_cash, menu.kcal, menu.menu, changed
                )

                print_flush(sql % values)
                cur.execute(sql % values)

                connection.commit()
            except Exception as error:
                connection.rollback()
                print_flush(error)

    finally:
        if connection:
            connection.close()


def parse_response(response):
    soup = BeautifulSoup(response.text, 'lxml-xml')
    rows = soup.find_all('Row')
    data = [parse_row(row) for row in rows][0]
    print_flush(data)

    # 식단이 미운영인 경우 (응답은 정상이나 식단이 없는 경우)
    if data is None:
        return None
    
    return MenuEntity(data['date'], data['dining_time'], data['place'], data['price_card'], data['price_cash'],
                      data['kcal'], json.dumps(data['menu'], ensure_ascii=False))


def get_menus(target_date: datetime, target_time: str = None):
    eat_types = ["breakfast", "lunch", "dinner"]
    restaurants = {"한식": "A코너", "일품": "B코너", "특식-전골/뚝배기": "C코너", "능수관": "능수관"}
    # campuses = ["Campus1", "Campus2"]

    cookie = get_cookie()
    date = target_date.strftime("%Y-%m-%d")
    menus = []

    menu_data = parse_response(send_request(cookie, date, eat_types[1], "한식", "Campus1"))
    if menu_data:
        menus.append(menu_data)
    """
    for eat_type in eat_types:
        for restaurant in restaurants:
            menus.append(parse_response(send_request(cookie, date, eat_type, restaurant, "Campus1")))
        menus.append(parse_response(send_request(cookie, date, eat_type, "코너1", "Campus2")))
    """

    return menus


def check_duplication_menu(existed_menu, new_menu):
    existed_menu = {(menu.date, menu.dining_time, menu.place): menu for menu in existed_menu}

    result = []

    for menu in new_menu:
        key = (menu.date, menu.dining_time, menu.place)
        if key not in existed_menu or existed_menu[key] != menu:
            result.append(menu)

    return result


def crawling():
    today = datetime.today()
    menus = get_menus((today + timedelta(days=0)))
    if menus is None or menus != [None]:
        update_db(menus)
    # for day in range(8):
    #    update_db(get_menus((today + timedelta(days=day))))


def loop_crawling(sleep=10):
    crawling()
    now_menus = get_menus(target_date=datetime.now(), target_time=check_meal_time())
    while meal_time := check_meal_time():
        time.sleep(sleep)

        now = datetime.now()
        print_flush(f"[{now}] {meal_time} 업데이트중...", end=" ", )

        menus = get_menus(target_date=now, target_time=meal_time)
        filtered = check_duplication_menu(now_menus, menus)

        print_flush("%s Found" % str(len(filtered)))
        if len(filtered) != 0:
            print_flush("메뉴 변경됨")

        for menu in filtered:
            print_flush(menu)

        update_db(filtered, is_changed=now)
        now_menus = menus


# execute only if run as a script
if __name__ == "__main__":
    # connection = connect_db()
    loop_crawling()
    # connection.close()
