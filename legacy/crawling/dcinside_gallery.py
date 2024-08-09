import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs
import pymysql
import json
import config

def connect_db():
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           port=config.DATABASE_CONFIG['port'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn

noticeIds = {
    "18":"CA001"
}

tags = {
    "CA001": "디씨크롤링"
}

def crawling(noticeId, ls=10):
    nas = []
    tag = noticeIds[noticeId]
    boardId = getBoardId(tag)

    host = "https://gall.dcinside.com"
    
    url = host + "/mgallery/board/lists/?id=koreatech&page=1"
    html = requests.get(url)
    soup = BeautifulSoup(html.text, "html.parser")
    trs = soup.select('#container > section.left_content > article:nth-child(3) > div.gall_listwrap.list > table > tbody > tr')

    for tr in trs:
        td = tr.select('td')
        # author
        author = td[2].text.split('(')[0].lstrip('\n')
        # title
        title = td[1].text.split('\n')[1]
        # permalink
        permalink = host+td[1].find('a').get('href')
        parsed_url = urlparse(permalink)
        qs = parse_qs(parsed_url.query)
        articleNum = qs.get('no')[0]

        na = DcArticle(boardId, title, author, articleNum, permalink)
        setContent(na)

        nas.append(na)

        print('updating... %s %s' % (tag, str(articleNum)))

    updateDB(nas)
    
    pass

def setContent(na):
    html = requests.get(na.permalink)
    soup = BeautifulSoup(html.text, "html.parser")
    
    content = soup.find('div', {'style':'overflow:hidden;'})
    content = str(content).replace('src="//', 'src="https://')
    content = str(content).replace('href="//', 'href="https://')
    content = re.sub("(<!--.*?-->)", "", str(content))

    registered_at = soup.find('span', {'class':'gall_date'}).get('title')
    
    na.content = content
    na.registered_at = registered_at
    pass

def getBoardId(tag):
    sql = "SELECT id FROM koin.boards WHERE tag = '%s'"
    cur = connection.cursor()
    cur.execute(sql % tag)
    rows = cur.fetchall()
    return rows[0][0] # db에 있는 boards의 id

def updateDB(nas):
    cur = connection.cursor()

    #추후 디씨 크롤링 등록시 sql문 테이블 변경 필요
    for na in nas:
        na.content = na.content.replace("'","""''""") #sql문에서 작은따옴표 이스케이프 처리
        try:
            sql = "INSERT INTO koin.notice_articles(board_id, title, content, author, hit, is_deleted, article_num, permalink, has_notice, registered_at) \
                VALUES (%d, '%s', '%s', '%s', %d, %d, %d, '%s', %d, '%s') \
                ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id), board_id = %d, article_num = %d"

            cur.execute(sql % (na.board_id, na.title, na.content, na.author, na.hit, na.is_deleted, int(na.article_num), na.permalink, na.has_notice, na.registered_at, na.board_id, int(na.article_num)))

            newNoticeId = cur.lastrowid
           
            meta = json.dumps({"registered_at": na.registered_at, "permalink": na.permalink})
          
            sql = "INSERT INTO koin.articles(board_id, title, nickname, content, user_id, ip, meta, is_notice, created_at, notice_article_id) \
                VALUES (%d, '%s', '%s', '%s', %d, '%s', '%s', %d, '%s', %d) \
                ON DUPLICATE KEY UPDATE board_id = %d, notice_article_id = %d"

            cur.execute(sql % (na.board_id, na.title, na.author, na.content, 0, "127.0.0.1", meta, 1, na.registered_at, newNoticeId, na.board_id, newNoticeId))
            connection.commit()

        except Exception as error:
            connection.rollback()
            print(error)

class DcArticle:
    def __init__(self, boardId, title, author, articleNum, permalink):
        self.board_id = boardId
        self.title = title
        self.content = None
        self.author = author
        self.hit = 0
        self.is_deleted = 0
        self.has_notice = 0
        self.article_num = articleNum
        self.permalink = permalink
        self.registered_at = None
        pass


if __name__ == "__main__":
    # execute only if run as a script
    connection = connect_db()
    for noticeId in noticeIds.keys():
        crawling(noticeId)
    connection.close()