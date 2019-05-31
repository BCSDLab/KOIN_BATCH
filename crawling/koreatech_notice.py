import requests
from bs4 import BeautifulSoup
import re
import urllib3
from urllib.parse import urlparse, parse_qs
import pymysql
import json
import config

def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn

noticeIds = {
    "14":"NA001",
    "15":"NA002",
    "16":"NA003",
    "17":"NA004"
}

tags = {
    "NA001": "일반공지",
    "NA002": "장학공지",
    "NA003": "학사공지",
    "NA004": "취업공지",
    "NA005": "코인공지"
}

def crawling(noticeId, ls=10):
    nas = []
    tag = noticeIds[noticeId]
    boardId = getBoardId(tag)

    if(noticeId == "17"):
        # 취업공지
        host = "https://job.koreatech.ac.kr"
        
        url = host + "/jobs/notice/jobNoticeList.aspx?page=1"
        html = requests.get(url, verify=False)
        soup = BeautifulSoup(html.text, "html.parser")

        trs = soup.select('table > tbody > tr')

        for tr in trs:
            td = tr.select('td')
            author = td[2].text
            title = td[3].text
            permalink = host + td[3].find('a').get('href')
            
            parsed_url = urlparse(permalink)
            qs = parse_qs(parsed_url.query)
            articleNum = qs.get('idx')[0]

            na = NoticeArticle(boardId, title, author, articleNum, permalink)
            setContentJob(na)

            nas.append(na)        

            print('updating... %s %s' % (tag, str(articleNum)))
    else:
        host = "https://portal.koreatech.ac.kr"    
             
        url = host + "/ctt/bb/bulletin?b=" + str(noticeId)
        html = requests.get(url, verify=False)
        soup = BeautifulSoup(html.text, "html.parser")

        trs = soup.select('table > tbody > tr')
    
        for tr in trs:
            permalink = host + tr.get('data-url')
            
            td = tr.select('td')
            articleNum = td[0].text.strip()
            title = td[1].text.strip()
            author = td[3].text.strip()
            
            na = NoticeArticle(boardId, title, author, articleNum, permalink)
            setContent(na)

            nas.append(na)
            print('updating... %s %s' % (tag, str(articleNum)))

    updateDB(nas)
    
    pass

def setContent(na):
    html = requests.get(na.permalink, verify=False)
    soup = BeautifulSoup(html.text, "html.parser")
    
    content = soup.find('div', class_= "bc-s-post-ctnt-area")
    registered_at = soup.find('table', class_= "kut-board-title-table").select('tbody > tr > td')[1].text.strip()
    content = str(content).replace('src="/ctt/', 'src="https://portal.koreatech.ac.kr/ctt/')

    na.content = re.sub("(<!--.*?-->)", "", str(content))
    na.registered_at = registered_at
    pass

def setContentJob(na):
    html = requests.get(na.permalink, verify=False)
    soup = BeautifulSoup(html.text, "html.parser")
    
    content = soup.find('tr', class_= "content")
    content = str(content).replace('src="/ctt/', 'src="https://portal.koreatech.ac.kr/ctt/')
    content = str(content).replace('src="/cheditors/', 'src="https://job.koreatech.ac.kr/cheditors/')
    content = re.sub("(<!--.*?-->)", "", str(content))
    
    registered_at = soup.findAll('tr', class_= "head")[1].find('td').text
    registered_at = str(registered_at)
    registered_at = registered_at[0:8] + registered_at[11:]
    
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

class NoticeArticle:
    def __init__(self, boardId, title, author, articleNum, permalink):
        self.board_id = boardId
        self.title = title
        self.content = None
        self.author = author
        self.hit = 0
        self.is_deleted = 0
        self.article_num = articleNum
        self.permalink = permalink
        self.has_notice = 0
        self.registered_at = None
        pass


if __name__ == "__main__":
    # execute only if run as a script
    connection = connect_db()
    for noticeId in noticeIds.keys():
        crawling(noticeId)
    connection.close()