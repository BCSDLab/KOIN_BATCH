import datetime
import json
import re
import time

import pymysql
import requests
from bs4 import BeautifulSoup

import config


def connect_db():
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn


extra_places = [
    "2캠퍼스",
]


class Coop:
    def __init__(self):
        self.__host = "http://coop.koreatech.ac.kr/dining/menu.php"
        self.__categories = []
        self.__set_categories()
        self.__categories.extend(extra_places)

    @property
    def host(self):
        return self.__host

    @property
    def categories(self):
        return self.__categories

    def __set_categories(self):
        html = requests.get(self.__host)
        html.encoding = 'UTF-8'

        soup = BeautifulSoup(html.content, features="html.parser")
        category = soup.find_all('td', 'menu-top')
        for i in category:
            if i.has_attr('colspan') or not i.text.strip():
                continue

            text = i.text if not i.select_one('td > strong > span') else \
                i.select_one('td > strong > span').text.replace('(', '').replace(')', '')
            self.__categories.append(text.strip())


def replace_escape_character(menu):
    return menu.replace("\\", "\\\\").replace("'", "\\'")


def datetime_to_YYYYMMDD(date):
    return date.strftime('%Y%m%d')


class MenuEntity:
    def __init__(self, date, dining_time, place, price_card, price_cash, kcal, menu):
        self.date = datetime_to_YYYYMMDD(date)
        self.dining_time = dining_time
        self.place = place
        self.price_card = price_card if price_card is not None else 'NULL'
        self.price_cash = price_cash if price_cash is not None else 'NULL'
        self.kcal = kcal if kcal is not None else 'NULL'
        self.menu = replace_escape_character(menu)

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


coop = Coop()


def filter_emoji(row):
    emoji_pattern = re.compile("["u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                               "]+", flags=re.UNICODE)

    return emoji_pattern.sub(r'', row)


def getMenus(target_date: datetime, target_time: set[str]):
    year, month, day = target_date.year, target_date.month, target_date.day
    chrono_time = int(time.mktime(datetime.datetime(year, month, day).timetuple()))

    url = '%s?sday=%s' % (coop.host, str(chrono_time))
    html = requests.get(url)
    html.encoding = 'UTF-8'

    soup = BeautifulSoup(html.content, features="html.parser")

    table = soup.select('table')[1]
    trs = table.select('tr')
    trs = trs[3:6]

    menus = []
    for tr in trs:
        tds = tr.select('td')
        dining_time = str(tds[0].text).strip().upper()

        if dining_time not in target_time:
            continue

        tds = tds[1:]

        for i, td in enumerate(tds):
            if i >= len(coop.categories):
                break

            span = td.find('span')
            if span is None:
                continue

            spanSplitted = str(span.text).split('/')
            # 에러나면 모두 null
            try:
                payCard = int(re.split('원', spanSplitted[0])[0].replace(',', ''))
            except ValueError:
                payCard = None

            try:
                payCash = int(re.split('원', spanSplitted[1])[0].replace(',', ''))
            except ValueError:
                payCash = None

            span.decompose()  # 가격은 위에서 파싱했으니 지우자
            content = list(td.stripped_strings)  # 공백 제거한 텍스트 반환
            cols = []

            contentIndex = 0
            hasKcal = False
            for row in content:
                if re.compile(r'^(\d*)kcal$').search(row):  # ~~kcal 형식이 발견되면
                    hasKcal = True
                    break
                row = filter_emoji(row)
                cols.append(row)
                contentIndex += 1

            kcal = re.split('kcal', content[contentIndex])[0] if hasKcal else None

            menu = MenuEntity(target_date, dining_time, coop.categories[i],
                              payCard, payCash, kcal, json.dumps(cols, ensure_ascii=False))
            menus.append(menu)

    return menus


def crawling(start_date: datetime = None, end_date: datetime = None, target_time=None):
    start_date = datetime.datetime.now() if start_date is None else start_date
    end_date = start_date + datetime.timedelta(days=7) if end_date is None or end_date < start_date else end_date
    target_time = {"BREAKFAST", "LAUNCH", "DINNER"} if target_time is None else target_time

    currentDate = start_date
    while currentDate <= end_date:
        print(currentDate)
        menus = getMenus(currentDate, target_time)

        print("%s Found" % str(len(menus)))
        for menu in menus:
            print(menu)

        updateDB(menus)
        currentDate += datetime.timedelta(days=1)


def updateDB(menus):
    cur = connection.cursor()

    for menu in menus:
        print("updating to DB..\n%s %s %s" % (menu.date, menu.dining_time, menu.place))
        try:
            # INT는 %s, VARCHAR은 '%s'로 표기 (INT에 NULL 넣기 위함)
            sql = """
            INSERT INTO koin.dining_menus(date, type, place, price_card, price_cash, kcal, menu)
            VALUES ('%s', '%s', '%s', %s, %s, %s, '%s')
            ON DUPLICATE KEY UPDATE price_card = %s, price_cash = %s, kcal = %s, menu = '%s'
            """

            values = (
                menu.date, menu.dining_time, menu.place, menu.price_card, menu.price_cash, menu.kcal, menu.menu,
                menu.price_card, menu.price_cash, menu.kcal, menu.menu
            )

            print(sql % values)
            cur.execute(sql % values)

            connection.commit()
        except Exception as error:
            connection.rollback()
            print(error)


def check_meal_time():
    def to_minute(hour):
        return hour * 60

    # 분 단위로 변환하여 계산
    now = datetime.datetime.now()
    minutes = to_minute(now.hour) + now.minute

    # 조식 08:00~09:30
    if to_minute(8) <= minutes <= to_minute(9) + 30:
        return "BREAKFAST"

    # 중식 11:30~13:30
    if to_minute(11) + 30 <= minutes <= to_minute(13) + 30:
        return "LAUNCH"

    # 석식 17:30~18:30
    if to_minute(17) + 30 <= minutes <= to_minute(18) + 30:
        return "DINNER"

    return ''


def loop_crawling(sleep=10):
    crawling()
    today = datetime.datetime.now()
    while meal_time := check_meal_time():
        print(f"{meal_time} 업데이트중...")
        time.sleep(sleep)
        crawling(start_date=today, end_date=today, target_time={meal_time})


# execute only if run as a script
if __name__ == "__main__":
    connection = connect_db()
    loop_crawling()
    connection.close()
