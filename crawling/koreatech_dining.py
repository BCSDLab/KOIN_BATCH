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


coop = Coop()


def getMenus(target_date: datetime):
    year, month, day = target_date.year, target_date.month, target_date.day
    chrono_time = int(time.mktime(datetime.datetime(year, month, day).timetuple()))

    url = f'{coop.host}?sday={str(chrono_time)}'
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
                cols.append(row)
                contentIndex += 1

            kcal = re.split('kcal', content[contentIndex])[0] if hasKcal else None

            menu = MenuEntity(target_date, dining_time, coop.categories[i],
                              payCard, payCash, kcal, json.dumps(cols, ensure_ascii=False))
            menus.append(menu)

    return menus


def crawling(start_date: datetime = None, end_date: datetime = None):
    start_date = datetime.datetime.now() if start_date is None else start_date
    end_date = start_date + datetime.timedelta(days=7) if end_date is None or end_date < start_date else end_date

    currentDate = start_date
    while currentDate <= end_date:
        print(currentDate)
        menus = getMenus(currentDate)

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
            sql = """
            INSERT INTO koin.dining_menus(date, type, place, price_card, price_cash, kcal, menu)
            VALUES ('%s', '%s', '%s', %s, %s, %s, '%s')
            ON DUPLICATE KEY UPDATE date = '%s', type = '%s', place = '%s'
            """

            print(sql % (
                menu.date, menu.dining_time, menu.place, menu.price_card, menu.price_cash, menu.kcal, menu.menu,
                menu.date, menu.dining_time, menu.place))

            menu.menu = menu.menu.replace("\\", "\\\\").replace("'", "\\'")
            cur.execute(sql % (
                menu.date, menu.dining_time, menu.place, menu.price_card, menu.price_cash, menu.kcal, menu.menu,
                menu.date, menu.dining_time, menu.place))

            connection.commit()
        except Exception as error:
            connection.rollback()
            print(error)


# execute only if run as a script
if __name__ == "__main__":
    connection = connect_db()
    crawling()
    connection.close()
