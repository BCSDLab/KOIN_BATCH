import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs
import pymysql
import datetime
import time
import json
import config

def connect_db():
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn

places = [
    "한식",
    "일품식",
    "특식",
    "양식",
    "능수관",
    "수박여",
    "2캠퍼스",
    "2캠퍼스-2"
]

def getMenus(currentDate):
    menus = []

    currentDate = currentDate.strftime("%Y-%m-%d")
    
    year = int(currentDate[0:4])
    month = int(currentDate[5:7])
    day = int(currentDate[8:10])

    # sday = datetime.datetime(year, month, day).strftime("%f")
    sday = int(time.mktime(datetime.datetime(year, month, day).timetuple()))

    host = "http://coop.koreatech.ac.kr/dining/menu.php"
             
    url = host + "?sday=" + str(sday)

    print(url)
    html = requests.get(url)
    # html.encoding = 'CP-949'
    html.encoding = 'UTF-8'
    
    # soup = BeautifulSoup(html.text, "html.parser")
    soup = BeautifulSoup(html.content, features="html.parser")

    table = soup.select('table')[1]
    trs = table.select('tr')
    trs = trs[3:6]

    for tr in trs:
        tds = tr.select('td')
        
        dtype = str(tds[0].text).strip().upper()
    
        tds = tds[1:]

        index = 0
        for td in tds:
            span = td.find('span')
            if span is None:
                index += 1
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

            menu = Menu(currentDate, dtype, places[index], payCard, payCash, kcal, json.dumps(cols))
            menus.append(menu)
            index += 1

    return menus

def crawling(startDate=None, endDate=None):
    if(startDate == None):
        startDate = datetime.datetime.today()
    else:
        year = int(startDate[0:4])
        month = int(startDate[5:7])
        day = int(startDate[8:10])

        startDate = datetime.datetime(year, month, day)

    if(endDate == None):
        endDate = startDate + datetime.timedelta(days=7)
    else:
        year = int(endDate[0:4])
        month = int(endDate[5:7])
        day = int(endDate[8:10])

        endDate = datetime.datetime(year, month, day)

    currentDate = startDate
    
    while(currentDate <= endDate):
        print(currentDate)
        menus = getMenus(currentDate)
        
        print("%s Found" % str(len(menus)))

        updateDB(menus)
        currentDate += datetime.timedelta(days=1)
        pass
    pass

class Menu:
    def __init__(self, date, dtype, place, price_card, price_cash, kcal, menu):
        self.date = date
        self.type = dtype
        self.place = place
        self.price_card = price_card if price_card is not None else 'NULL'
        self.price_cash = price_cash if price_cash is not None else 'NULL'
        self.kcal = kcal if kcal is not None else 'NULL'
        self.menu = menu
        pass

def updateDB(menus):
    cur = connection.cursor()

    for menu in menus:
        print("updating to DB.. %s %s %s" % (menu.date, menu.type, menu.place))
        try:
            sql = """
            INSERT INTO koin.dining_menus(date, type, place, price_card, price_cash, kcal, menu)
            VALUES ('%s', '%s', '%s', %s, %s, %s, '%s')
            ON DUPLICATE KEY UPDATE date = '%s', type = '%s', place = '%s'
            """
            
            print(sql % (menu.date, menu.type, menu.place, menu.price_card, menu.price_cash, menu.kcal, menu.menu, menu.date, menu.type, menu.place))
            
            print(menu.kcal)
            print(menu.menu.encode('utf-8').decode('unicode_escape'))
            print(menu.price_card)
            print(menu.price_cash)
            menu.menu = menu.menu.replace("\\", "\\\\").replace("'", "\\'")
            cur.execute(sql % (menu.date, menu.type, menu.place, menu.price_card, menu.price_cash, menu.kcal, menu.menu, menu.date, menu.type, menu.place))

            connection.commit()
        except Exception as error:
            connection.rollback()
            print(error)

if __name__ == "__main__":
    # execute only if run as a script
    connection = connect_db()
    crawling()
    connection.close()


