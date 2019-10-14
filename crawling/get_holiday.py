from bs4 import BeautifulSoup
import requests
from datetime import datetime
import urllib3
import pymysql
import config


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn


def crawling():
    now = datetime.now()
    authorize_key = 'tooGWOzbehkPmBairI8NF5qHCgPMkE7cFrHNNKRiqLBeC4Pyy7paCQbEeV0Xgt2vBp2YUWGlSxpHuc6vkcAlIQ%3D%3D'

    for i in range(1, 13):
        url = "http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo?serviceKey=%s&solYear=%d" \
              "&solMonth=%02d" % (authorize_key, now.year, i)
        request = requests.get(url)
        request.encoding = 'UTF-8'

        soup = BeautifulSoup(request.content, features="html.parser")

        header = soup.find('header')
        if header is None:  # 에러 시 넘김
            print("%d월 에러 발생: None" % i)
            continue

        resultCode = header.find('resultcode')
        resultMessage = header.resultmsg

        if resultCode.text != '00':  # 정상 코드가 아니면 넘김
            print("%d월 에러 발생: %s" % (i, resultMessage.text))
            continue

        body = soup.body
        items = body.findAll('item')
        for item in items:
            name = item.datename.text
            date = item.locdate.text
            print(name, date)
            # updateDB(name, date)
    pass


def updateDB(name, date):
    cur = connection.cursor()
    try:
        sql = "INSERT INTO koin.holidays(NAME, DATE) VALUES ('%s', '%s')"
        print(sql % (name, date))

        cur.execute(sql % (name, date))
        connection.commit()

    except Exception as error:
        connection.rollback()
        print(error)


if __name__ == "__main__":
    connection = connect_db()
    crawling()
    connection.close()
