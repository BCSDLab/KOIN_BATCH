import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs
import pymysql
import config

def connect_db():
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           port=config.DATABASE_CONFIG['port'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'])
    return conn

def crawling():
    cs = []

    url = "https://www.koreatech.ac.kr/prog/schedule/kor/sub04_01_01_01/1/haksa.do"
    
    html = requests.get(url, verify=False)
    soup = BeautifulSoup(html.text, "html.parser")
    
    table = soup.find('div', class_= 'schedule_table_web')
    trs = table.select('table > tbody > tr')

    year = soup.find('div', class_= 'schdule_title').find('p').text[:4]
    
    seq = 0
    
    for tr in trs:
        seq += 1

        th = tr.find('th')

        if(th != None):
            month = str(th.text[:-1])
            month = "%02d" % (int(month))
        
        tds = tr.select('td')

        calendar = Calendar(year, None, None, None, None, None, seq, None)

        date = tds[0].text
        schedule = tds[1].text
        dates = str(date).split('~')
        
        if(len(dates) == 2):
            calendar.start_month = month
            calendar.start_day = dates[0]
            calendar.schedule = schedule
            calendar.is_continued = 1

            endDates = str(dates[1]).split('.')
            cnt = len(endDates)
            if(cnt == 1):
                calendar.end_month = month
                calendar.end_day = endDates[0]
            elif(cnt == 2):
                calendar.end_month = endDates[0]
                calendar.end_day = endDates[1]
        else:
            calendar.start_month = month
            calendar.end_month = month
            calendar.start_day = date
            calendar.end_day = date
            calendar.schedule = schedule
            calendar.is_continued = 0

        cs.append(calendar)
        print('updating %s - %s %s' % (str(calendar.year), str(calendar.start_month), str(seq)))

    updateDB(cs)
    pass


def updateDB(cs):
    cur = connection.cursor()

    for c in cs:
        try:
            sql = "INSERT INTO koin.calendar_universities(year, start_month, end_month, start_day, end_day, schedule, seq, is_continued) \
                VALUES ('%s', '%s', '%s', '%s', '%s', '%s', %s, %s) \
                ON DUPLICATE KEY UPDATE year = %s, seq = %s"

            cur.execute(sql % (c.year, c.start_month, c.end_month, c.start_day, c.end_day, c.schedule, c.seq, c.is_continued, c.year, c.seq))
           
            connection.commit()
        except Exception as error:
            connection.rollback()
            print(error)

class Calendar:
    def __init__(self, year, startMonth, endMonth, startDay, endDay, schedule, seq, isContinued):
        self.year = year
        self.start_month = startMonth
        self.end_month = endMonth
        self.start_day = startDay
        self.end_day = endDay
        self.schedule = schedule
        self.seq = seq
        self.is_continued = isContinued

if __name__ == "__main__":
    # execute only if run as a script
    connection = connect_db()
    crawling()
    connection.close()
