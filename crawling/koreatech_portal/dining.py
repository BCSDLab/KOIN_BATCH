import json
import re
import time
from datetime import datetime, timedelta

import pymysql
import pytz
import redis as redis_library
import requests
from bs4 import BeautifulSoup

import config
from login import portal_login

"""
동작 과정
1. 아우누리 식단을 크롤링한다.
    1. redis에 저장된 쿠키가 있으면 사용한다.
    2. redis에 저장된 쿠키가 없으면 아우누리에 로그인하여 쿠키를 저장한다.
2. 크롤링한 식단 정보를 DB에 저장한다.
    1. DB에 저장된 식단 정보와 비교하여 변경된 식단이 있으면 업데이트한다.
    2. 이 때는 식단이 변경되어도 is_changed를 업데이트하지 않는다.
    3. 식단에 '천원의 아침'이 포함되어있으면 image_url에 천원의 아침 이미지 url을 삽입한다.
3. 현재 시간이 식사 시간인지 확인한다.
4. 식사시간이 아니면 종료된다.
5. 식사시간이면 현재 식사시간 메뉴를 크롤링한다.
6. 이전에 크롤링했던 메뉴 정보와 새로 크롤링한 메뉴 정보를 비교한다.
7. 변경된 메뉴가 있으면 DB를 업데이트한다.
    1. 이 때는 is_changed를 현재 시간으로 업데이트한다.
8. 식사시간이 끝날 때까지 5번부터 반복한다.
"""

redis_client = None
mysql_connection = None
KST = pytz.timezone('Asia/Seoul')


# 식단 메뉴 정보를 담는 클래스
class MenuEntity:
    def __init__(self, date, dining_time, place, price_card, price_cash, kcal, menu, image_url):
        self.date = date
        self.dining_time = dining_time
        self.place = place
        self.price_card = price_card or 'NULL'
        self.price_cash = price_cash or 'NULL'
        self.kcal = kcal or 'NULL'
        self.menu = menu
        self.image_url = image_url

    def __str__(self):
        return '%s, %s, %s, %s, %s, %s, %s' % (
            self.dining_time, self.place, self.price_card, self.price_cash, self.kcal, self.menu, self.image_url
        )

    def __repr__(self):
        return '%s, %s, %s, %s, %s, %s, %s' % (
            self.dining_time, self.place, self.price_card, self.price_cash, self.kcal, self.menu, self.image_url
        )

    def __eq__(self, other):
        if isinstance(other, MenuEntity):
            return self.date == other.date and \
                self.dining_time == other.dining_time and \
                self.place == other.place and \
                self.price_card == other.price_card and \
                self.price_cash == other.price_cash and \
                self.kcal == other.kcal and \
                self.menu == other.menu and \
                self.image_url == other.image_url

        return False


# flush=True로 출력 (지연 출력 방지)
def print_flush(target):
    print(target, flush=True)


# 아우누리 포탈에 식단 정보 요청
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
        return response
    # 잘못된 쿠키 사용 예외 던지기
    raise ConnectionError("식단 요청 실패")


# 레디스 연결
def connect_redis():
    # Redis 클라이언트 생성
    host = config.REDIS_CONFIG['host']
    port = config.REDIS_CONFIG['port']
    db = config.REDIS_CONFIG['db']
    password = config.REDIS_CONFIG['password']
    redis = redis_library.StrictRedis(host=host, port=port, db=db, password=password)

    # 연결 테스트
    try:
        redis.ping()
        return redis
    except redis_library.ConnectionError:
        raise ConnectionError("레디스 연결 불가")


# MySQL 연결
def connect_mysql():
    return pymysql.connect(
        host=config.MYSQL_CONFIG['host'],
        port=config.MYSQL_CONFIG['port'],
        user=config.MYSQL_CONFIG['user'],
        password=config.MYSQL_CONFIG['password'],
        db=config.MYSQL_CONFIG['db'],
        charset='utf8',
        cursorclass=pymysql.cursors.DictCursor
    )


# 로그인 쿠키 취득
def get_cookie():
    # redis 캐시 조회
    global redis_client
    login_cookie = redis_client.get('__KSMSID__')
    if login_cookie:
        login_cookie = login_cookie.decode("utf-8")
        try:
            send_request(login_cookie, datetime.today().strftime("%Y-%m-%d"), "lunch", "한식", "Campus1")
            return login_cookie
        except ConnectionError:
            pass

    # 아우누리 로그인하여 쿠키 취득
    login_cookie = portal_login()['__KSMSID__']
    redis_client.set('__KSMSID__', login_cookie)
    return login_cookie


# 식단 정보 파싱
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
        # '\t', '\r' 제거 및 다중 공백 제거
        dish_text = re.sub(r'[\t\r]', ' ', dish_text)
        # 마지막 칼로리 정보 및 가격 정보 제거
        dish_text = re.sub(r'\d+ kcal.*', '', dish_text).strip()
        dish_text = re.sub(r'\d+ 원.*', '', dish_text).strip()
        # 줄바꿈 기준으로 메뉴를 구분
        dishes = [dish.strip() for dish in dish_text.split('\n') if dish]
        return dishes

    def parse_price(price_text):
        # 쉼표와 공백 제거 후 가격 추출
        prices = re.findall(r'\d+', price_text.replace(',', ''))
        # 가격이 두 개 이상일 경우 첫 번째와 두 번째 값을 반환
        if len(prices) >= 2:
            return int(prices[0]), int(prices[1])
        else:
            return int(prices[0]), int(prices[0]) if prices else (None, None)

    def parse_place(place_description):
        places = {"한식": "A코너", "일품": "B코너", "특식-전골/뚝배기": "C코너", "능수관": "능수관", "1코너": "1코너"}
        for key in places.keys():
            if key in place_description:
                return places[key]
        return place_description  # 기본적으로 동일한 값 반환

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
    except Exception as e:
        return None


# 현재 어떤 식사 시간인지 확인
def check_meal_time():
    def to_minute(hour):
        return hour * 60

    # 분 단위로 변환하여 계산
    now = datetime.now().astimezone(KST)
    minutes = to_minute(now.hour) + now.minute

    # 조식 08:00~09:30
    if to_minute(8) <= minutes <= to_minute(9) + 30:
        return "breakfast"

    # 중식 11:30~13:30
    if to_minute(11) + 30 <= minutes <= to_minute(13) + 30:
        return "lunch"

    # 석식 17:30~18:30
    if to_minute(17) + 30 <= minutes <= to_minute(18) + 30:
        return "dinner"

    return ''


# 아직 남은 식사 시간을 반환
def get_remaining_meal_times():
    now = datetime.now().astimezone(KST)
    remaining_meal_times = []

    breakfast_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
    lunch_start = now.replace(hour=11, minute=30, second=0, microsecond=0)
    dinner_start = now.replace(hour=17, minute=30, second=0, microsecond=0)

    if now < breakfast_start:
        remaining_meal_times.append("breakfast")
    if now < lunch_start:
        remaining_meal_times.append("lunch")
    if now < dinner_start:
        remaining_meal_times.append("dinner")

    return remaining_meal_times


# MySQL DB에 크롤링한 식단 정보 업데이트
def update_db(menus, is_changed=None):
    global mysql_connection
    try:
        cur = mysql_connection.cursor()
        for menu in menus:
            print_flush("updating to DB..\n%s %s %s" % (menu.date, menu.dining_time, menu.place))
            try:
                # INT는 %s, VARCHAR은 '%s'로 표기 (INT에 NULL 넣기 위함)
                sql = """
                INSERT INTO koin.dining_menus(date, type, place, price_card, price_cash, kcal, menu, image_url, is_changed)
                VALUES ('%s', '%s', '%s', %s, %s, %s, '%s', %s, NULL)
                ON DUPLICATE KEY UPDATE price_card = %s, price_cash = %s, kcal = %s, menu = '%s', is_changed = %s
                """

                changed = is_changed.strftime('"%Y-%m-%d %H:%M:%S"') if is_changed else "NULL"
                image_url = f'"{menu.image_url}"' if menu.image_url else "NULL"

                values = (
                    menu.date, menu.dining_time.upper(), menu.place, menu.price_card, menu.price_cash, menu.kcal,
                    menu.menu, image_url,
                    menu.price_card, menu.price_cash, menu.kcal, menu.menu, changed
                )

                print_flush(sql % values)
                cur.execute(sql % values)

                mysql_connection.commit()
            except Exception as error:
                mysql_connection.rollback()
                print_flush(error)

    finally:
        cur.close()


# 크롤링 데이터를 메뉴 객체로 변환
def parse_response(response):
    soup = BeautifulSoup(response.text, 'lxml-xml')
    rows = soup.find_all('Row')
    data = [parse_row(row) for row in rows]

    # 응답은 정상이나 식단이 없는 경우 (아직 올라오지 않은 식단)
    if data is None or len(data) == 0 or data[0] is None:
        return None

    menu = data[0]

    image_url = None
    if '천원의아침' in json.dumps(menu['menu'], ensure_ascii=False):
        image_url = "https://team-kap-koin-storage.s3.ap-northeast-2.amazonaws.com/dining/%EC%B2%9C%EC%9B%90%EC%9D%98%EC%95%84%EC%B9%A8.png"

    return MenuEntity(menu['date'], menu['dining_time'], menu['place'], menu['price_card'], menu['price_cash'],
                      menu['kcal'], json.dumps(menu['menu'], ensure_ascii=False), image_url)


# 메뉴 정보를 요청하여 메뉴 리스트 반환
# target_time이 None이면 모든 식사 시간에 대해 크롤링
# target_time이 있으면 해당 식사 시간에 대해서만 크롤링
def get_menus(target_date: datetime, target_time: str = None):
    eat_types = ["breakfast", "lunch", "dinner"]
    restaurants = {"한식": "A코너", "일품": "B코너", "특식-전골/뚝배기": "C코너", "능수관": "능수관"}
    # campuses = ["Campus1", "Campus2"]

    cookie = get_cookie()
    date = target_date.strftime("%Y-%m-%d")
    menus = []

    for eat_type in eat_types:
        if target_time and eat_type != target_time:
            continue
        for restaurant in restaurants:
            menu_data = parse_response(send_request(cookie, date, eat_type, restaurant, "Campus1"))
            if menu_data:
                menus.append(menu_data)
        menu_data = parse_response(send_request(cookie, date, eat_type, "코너1", "Campus2"))
        if menu_data:
            menus.append(menu_data)

    return menus


# 기존 메뉴와 현재 메뉴가 다른지 확인
def check_duplication_menu(existed_menu, new_menu):
    existed_menu = {(menu.date, menu.dining_time, menu.place): menu for menu in existed_menu}
    result = []
    for menu in new_menu:
        key = (menu.date, menu.dining_time, menu.place)
        if key not in existed_menu or existed_menu[key] != menu:
            result.append(menu)
    return result


# 일주일 식단 전체 크롤링
def crawling():
    today = datetime.today()
    remaining_meal_times = get_remaining_meal_times()

    # 오늘의 식단 중 지나거나 진행중인 식사 시간은 크롤링하지 않음
    # 크롤링하게 되면 DB에 덮어씌워지는데, 이 때 is_changed가 사라져버림
    for meal_time in remaining_meal_times:
        menus = get_menus(today, meal_time)
        if menus is None or menus != [None]:
            update_db(menus)

    for day in range(1, 7):
        menus = get_menus((today + timedelta(days=day)))
        if menus is None or menus != [None]:
            update_db(menus)


# 현재 식사 시간에 대해서만 크롤링하고 변경 감지 시 DB 업데이트
# 실행 시간이 식사 시간인 경우에만 호출됨
def loop_crawling(sleep=10):
    crawling()
    now_menus = get_menus(target_date=datetime.now().astimezone(KST), target_time=check_meal_time())
    while meal_time := check_meal_time():
        time.sleep(sleep)

        now = datetime.now().astimezone(KST)
        menus = get_menus(target_date=now, target_time=meal_time)
        filtered = check_duplication_menu(now_menus, menus)

        print_flush(f"[{now}] {meal_time} 업데이트중... %s Found" % str(len(filtered)))
        if len(filtered) != 0:
            print_flush("메뉴 변경됨")

        for menu in filtered:
            print_flush(menu)

        update_db(filtered, is_changed=now)
        now_menus = menus


# execute only if run as a script
if __name__ == "__main__":
    redis_client = connect_redis()
    mysql_connection = connect_mysql()
    try:
        loop_crawling()
    finally:
        mysql_connection.close()
