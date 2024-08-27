from typing import Optional, List

from config import MYSQL_CONFIG

import requests
from bs4 import BeautifulSoup, Comment
import urllib3
import pymysql
from table import replace_table
from login import login
from crawling.slack_notice import filter_nas, notice_to_slack


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=MYSQL_CONFIG['host'],
                           port=MYSQL_CONFIG['port'],
                           user=MYSQL_CONFIG['user'],
                           password=MYSQL_CONFIG['password'],
                           db=MYSQL_CONFIG['db'],
                           charset='utf8')
    return conn


class Board:
    def __init__(
        self,
        bulletin: int,
        name: str,
        s3: str,
        is_notice: bool,
        need_login: bool
    ):
        self._id = None
        self.bulletin = bulletin
        self.name = name
        self.s3 = s3
        self.is_notice = is_notice
        self.need_login = need_login

    @property
    def id(self) -> Optional[int]:
        """
        id를 최초 조회할 때 db 조회해서 가져옴
        :return: board.id
        """
        if self._id is None:
            self._id = self._get_id()
        return self._id

    def _get_id(self):
        """
        id를 조회할 때 최초 1번 실행
        :return: db에 있는 boards의 id
        """
        sql = f"SELECT id FROM koin.boards WHERE name = '{self.name}'"
        cur = connection.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        return rows[0][0]


class Attachment:
    def __init__(
        self,
        name: str,
        url: str
    ):
        self.name = name
        self.url = url


class ArticleComment:
    def __init__(
        self,
        author: str,
        content: str,
        registered_at: str
    ):
        self.author = author
        self.content = content
        self.registered_at = registered_at


class Article:
    def __init__(
        self,
        url: str,
        board_id: int,
        num: int,
        title: str,
        content: str,
        author: str,
        hit: int,
        registered_at: str,
        attachment: List[Attachment],
        comment: Optional[List[ArticleComment]] = None
    ):
        self.url = url
        self.board_id = board_id
        self.num = num
        self.title = title
        self.content = content
        self.author = author
        self.hit = hit
        self.registered_at = registered_at
        self.attachment = attachment
        self.comment = comment

    def payload(self):
        return {'board_id': self.board_id, 'article_num': self.num}

    def __str__(self):
        return str({'board_id': self.board_id, 'article_num': self.num})

    def __repr__(self): return self.__str__()


boards = [
    Board(14, "일반공지", "general_notice", True, False),
    Board(15, "장학공지", "scholarship_notice", True, False),
    Board(16, "학사공지", "academic_notice", True, False),
    Board(151, "현장실습공지", "field_training_notice", True, True),
    Board(21, "학생생활", "student_life", False, True),
    Board(17, "취업공지", "job_notice", True, True),
]


def get_cookies(board: Board):
    if not board.need_login:
        return None

    return {
        'JSESSIONID': login_cookie['JSESSIONID']['value'],
        'mauth': login_cookie['mauth']['value'],
        'hn_ck_login': login_cookie['hn_ck_login']['value'],
    }


def crawling(board: Board, list_size: int) -> List[Article]:
    articles = []

    host = f"https://portal.koreatech.ac.kr"
    path = f"/ctt/bb/bulletin?b={board.bulletin}&ls={list_size}&dm=m"

    html = requests.get(host + path, cookies=get_cookies(board), verify=False)
    soup = BeautifulSoup(html.text, "html.parser")

    articles_html = soup.select('table#boardTypeList > tbody > tr')

    for article_html in articles_html:
        url = host + article_html.get('data-url')

        article = crawling_article(board, host, url)
        articles.append(article)

        print(f'find... {board.name} {article.num}')

    return articles


def crawling_article(board: Board, host: str, url: str) -> Article:
    html = requests.get(url, cookies=get_cookies(board), verify=False)
    soup = BeautifulSoup(html.text, "html.parser")

    # ===== 글 번호 =====
    num = int(url.rsplit("=", 1)[1])

    # ===== 제목 =====
    head = soup.select_one('table.kut-board-title-table')
    title = head.select_one('thead > tr > th').get_text(separator=" ", strip=True)

    # ===== 작성자, 작성일, 조회수 =====
    author, registered_at, hit = map(
        lambda tag: tag.get_text(strip=True),
        head.select('tbody > tr > td')
    )

    # ===== 본문 =====
    head = soup.select_one('head')
    body = soup.select_one('div.bc-s-post-ctnt-area')
    content = soup.new_tag('div')
    content.extend([head, body])

    # 주석 제거
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 이미지 url 처리
    content = (str(content)
               .replace('src="/', f'src="{host}/')
               .replace('href="/', f'href="{host}/'))

    # 표 처리
    content = replace_table(content, board, num)

    # ===== 첨부 파일 =====
    attachment = list(map(
        lambda tag: Attachment(
            name=(a_tag := tag.select_one('dt.tx-name > a')).get_text(strip=True),
            url=host + a_tag.get('href')
        ),
        soup.select('ul#tx_attach_list > li')
    ))

    return Article(
        url=url,
        board_id=board.id,
        num=num,
        title=title,
        content=content,
        author=author,
        hit=hit,
        registered_at=registered_at,
        attachment=attachment,
        comment=None  # comment는 없어도 됨. 명시적으로 작성
    )


# 취업 공지
def crawling_job(board: Board, page_size: int):
    articles = []

    host = "https://job.koreatech.ac.kr"

    for page in range(1, page_size+1):
        path = f"/Community/Notice/NoticeList.aspx?rp={page}"

        html = requests.get(host + path, cookies=get_cookies(board), verify=False)
        soup = BeautifulSoup(html.text, "html.parser")

        articles_html = soup.select('table#tbody_list1 > tbody > tr')

        for article_html in articles_html:
            onclick = article_html.select_one('a[onclick]').get('onclick')
            url = host + onclick.split("'")[1]

            article = crawling_job_article(board, host, url)
            articles.append(article)

            print(f'find... {board.name} {article.num}')

    return articles


def crawling_job_article(board: Board, host: str, url: str) -> Article:
    html = requests.get(url, cookies=get_cookies(board), verify=False)
    soup = BeautifulSoup(html.text, "html.parser")

    # ===== 글 번호 =====
    num = int(url.rsplit("=", 1)[1])

    # ===== 제목 =====
    title = soup.select_one('span#title').get_text(strip=True)

    # ===== 작성자 =====
    author = soup.select_one('span#wuser').get_text(strip=True)

    # ===== 작성일 =====
    registered_at = soup.select_one('span#wdate').get_text(strip=True)

    # ===== 본문 =====
    head = soup.select_one('head')
    body = soup.select_one('div#wcontent')
    content = soup.new_tag('div')
    content.extend([head, body])

    # 주석 제거
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # 이미지 url 처리
    content = (str(content)
               .replace('src="/', f'src="{host}/')
               .replace('href="/', f'href="{host}/'))

    # 표 처리
    content = replace_table(content, board, num)

    # ===== 첨부 파일 =====
    attachment = list(map(
        lambda tag: Attachment(
            name=tag.get_text(strip=True),
            url=host + tag.get('href')
        ),
        soup.select('span#Downloader_fileList > a')
    ))

    return Article(
        url=url,
        board_id=board.id,
        num=num,
        title=title,
        content=content,
        author=author,
        hit=0,
        registered_at=registered_at,
        attachment=attachment
    )


def update_db(articles):
    cur = connection.cursor()

    for article in articles:
        article.content = article.content.replace("'", """''""")  # sql문에서 작은따옴표 이스케이프 처리
        article.title = article.title.replace("'", """''""")  # sql문에서 작은따옴표 이스케이프 처리
        try:
            notice_sql = f"""
INSERT INTO koin.koreatech_articles(
    url, board_id, article_num,
    title, content, author,
    hit, attachment, registered_at
)
VALUES (
    '{article.url}', {article.board_id}, {article.num},
    '{article.title}', '{article.content}', '{article.author}',
    {article.hit}, '{article.attachment}', '{article.registered_at}'
)
ON DUPLICATE KEY UPDATE
title = '{article.title}', content = '{article.content}', author = '{article.author}',
attachment = '{article.attachment}', article.hit = {article.hit}"""

            cur.execute(notice_sql)
            print("ARTICLE_QUERY :", article.board_id, article.title, article.author)

            connection.commit()

        except Exception as error:
            connection.rollback()
            print(error)


if __name__ == "__main__":
    # execute only if run as a script
    LIST_SIZE = 60

    articles = []
    bus_articles = []
    new_articles = []

    connection = connect_db()
    login_cookie = login()
    for board in boards:
        board_articles = (
            crawling_job(board, page_size=LIST_SIZE // 10)
            if board.name == "취업공지"
            else
            crawling(board, list_size=LIST_SIZE)
        )

        print(board_articles)

        articles.extend(board_articles)

        # 버스 알림
        if board.is_notice:
            # DB에 없고, 키워드가 들어있는 게시글 필터링
            bus_articles.extend(filter_nas(connection, board_articles, keywords={"버스", "bus"}))

        new_articles.extend(filter_nas(connection, board_articles))

        update_db(board_articles)

    connection.close()

    if bus_articles:
        notice_to_slack(bus_articles)

    if new_articles:
        payload = {
            'update_notification': list(map(lambda article: article.payload(), new_articles))
        }

        requests.post(
            "https://api.koreatech.in/articles/keyword/notification",
            json=payload
        )

