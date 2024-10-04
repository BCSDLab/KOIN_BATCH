from typing import Optional, List

from config import MYSQL_CONFIG
from config import BATCH_CONFIG

from emoji import core
import requests
from bs4 import BeautifulSoup, Comment
import urllib3
import pymysql
from table import replace_table
from login import login
from login import get_jwt_token
from slack_notice import filter_nas, notice_to_slack

from math import ceil
from hashlib import sha256

import builtins
from dateutil import parser


def print(*args, **kwargs):
    kwargs['flush'] = True
    return builtins.print(*args, **kwargs)


def removeprefix(string, prefix):
    if string.startswith(prefix):
        return string[len(prefix):]
    return string


"""

[TODO]

table을 해시화 --> redis에 저장. 유효기간 10분으로 잡고
다르면 --> 표 이미지화를 '비동기로 진행'

"""


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
        url: str,
        _hash: Optional[str] = None
    ):
        self.name = name
        self.url = url
        self._hash = _hash

    @property
    def hash(self):
        if self._hash is None:
            response = requests.get(self.url, stream=True)
            response.raise_for_status()

            sha256_hash = sha256()
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    sha256_hash.update(chunk)

            self._hash = sha256_hash.hexdigest().upper()

        return self._hash

    def __hash__(self) -> int:
        return hash(self.hash)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Attachment):
            return False

        return self.hash == other.hash


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
        is_notice: bool,
        comment: Optional[List[ArticleComment]] = None
    ):
        self._id = None
        self.url = url
        self.board_id = board_id
        self.num = num
        self.title = title
        self.content = content
        self.author = author
        self.hit = hit
        self.registered_at = registered_at
        self.attachment = attachment
        self.is_notice = is_notice
        self.comment = comment

    @property
    def id(self) -> Optional[int]:
        """
        id를 최초 조회할 때 db 조회해서 가져옴
        :return: board.id
        """
        if self._id is None:
            self._id = self._get_id()
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    def _get_id(self):
        """
        id를 조회할 때 최초 1번 실행
        :return: db에 있는 articles의 id
        """
        sql = f"SELECT a.id FROM koin.articles a JOIN koin.koreatech_articles b ON a.id = b.article_id WHERE a.board_id = '{self.board_id}' AND b.portal_num = '{self.num}'"
        cur = connection.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        return rows[0][0]

    def payload(self):
        return {'board_id': self.board_id, 'portal_num': self.num}

    def __str__(self):
        return str({'board_id': self.board_id, 'portal_num': self.num})

    def __repr__(self): return self.__str__()


boards = [
    Board(14, "일반공지", "general_notice", True, False),
    Board(15, "장학공지", "scholarship_notice", True, False),
    Board(17, "취업공지", "job_notice", True, True),
    Board(16, "학사공지", "academic_notice", True, False),
    Board(151, "현장실습공지", "field_training_notice", True, True),
    Board(21, "학생생활", "student_life", False, True),

]


def get_cookies(board: Board):
    if not board.need_login:
        return None

    return {
        'JSESSIONID': login_cookie['JSESSIONID']['value'],
        'ASP.NET_SessionId': login_cookie['ASP.NET_SessionId']['value'],
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
    title = removeprefix(title, '[일반공지]').strip()

    # ===== 작성자, 작성일, 조회수 =====
    author, registered_at, hit = map(
        lambda tag: tag.get_text(strip=True),
        head.select('tbody > tr > td')
    )

    # ===== 본문 =====
    head = soup.select_one('head')
    body = soup.select_one('div.bc-s-post-ctnt-area')
    content = soup.new_tag('html')
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
        is_notice=board.is_notice,
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
    body = soup.select_one('#content')
    content = soup.new_tag('html')
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
        attachment=attachment,
        is_notice=board.is_notice,
        comment=None  # comment는 없어도 됨. 명시적으로 작성
    )


def update_db(articles):
    cur = connection.cursor()

    for article in articles[::-1]:
        article.title = core.replace_emoji(article.title, replace='')
        article.title = article.title.replace("'", """''""")  # sql문에서 작은따옴표 이스케이프 처리

        article.content = core.replace_emoji(article.content, replace='')
        article.content = article.content.replace("'", """''""")  # sql문에서 작은따옴표 이스케이프 처리

        article.author = core.replace_emoji(article.author, replace='')

        for attachment in article.attachment:
            attachment.name = core.replace_emoji(attachment.name, replace='')

        article.registered_at = parser.parse(article.registered_at).strftime("%Y-%m-%d %H:%M:%S")

        try:
            # 먼저 존재 여부 확인
            cur.execute("""
                        SELECT a.id
                        FROM koin.articles a
                        JOIN koin.koreatech_articles ka ON a.id = ka.article_id
                        WHERE a.board_id = %s AND ka.portal_num = %s
                    """, (article.board_id, article.num))

            result = cur.fetchone()

            if result:
                # 데이터가 존재하면 업데이트
                cur.execute("""
                            UPDATE koin.articles
                            SET title = %s, content = %s, hit = %s, is_notice = %s
                            WHERE id = %s
                        """, (article.title, article.content,
                              article.hit, article.is_notice, article.id))

                cur.execute("""
                            UPDATE koin.koreatech_articles
                            SET url = %s, author = %s, registered_at = %s
                            WHERE article_id = %s
                        """, (article.url, article.author,
                              article.registered_at, article.id))
            else:
                # 데이터가 존재하지 않으면 삽입
                cur.execute("""
                            INSERT INTO koin.articles (board_id, title, content, hit, is_notice)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (article.board_id, article.title, article.content,
                              article.hit, article.is_notice))

                article.id = cur.lastrowid

                cur.execute("""
                            INSERT INTO koin.koreatech_articles (article_id, url, portal_num, author, registered_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (article.id, article.url, article.num,
                              article.author, article.registered_at))

            connection.commit()

            print("ARTICLE_QUERY :", article.board_id, article.title, article.author)

        except Exception as error:
            connection.rollback()
            print(error)

        try:
            # 기존 첨부파일 조회
            cur.execute(
                """
                SELECT id, name, url, HEX(hash) FROM koin.article_attachments 
                WHERE article_id = %s AND is_deleted = 0
                """,
                article.id
            )
            existing_attachments = {Attachment(row[1], row[2], row[3]) for row in cur.fetchall()}

            new_attachments = set(article.attachment)

            deleted = existing_attachments - new_attachments
            # 첨부파일 삭제 처리
            if deleted:
                deleted_names = [attach.name for attach in deleted]
                cur.execute(
                    """
                    UPDATE koin.article_attachments 
                    SET is_deleted = 1
                    WHERE article_id = %s AND HEX(hash) IN %s
                    """,
                    (article.id, tuple(deleted_names))
                )

            # 첨부파일 추가
            for attachment in new_attachments:
                attachment_sql = """
                    INSERT INTO koin.article_attachments(article_id, hash, url, name)
                    VALUES (%s, UNHEX(%s), %s, %s)
                    ON DUPLICATE KEY UPDATE
                        url = %s, name = %s
                """

                cur.execute(
                    attachment_sql,
                    (
                        article.id, attachment.hash, attachment.url, attachment.name,
                        attachment.url, attachment.name
                    )
                )
                print("ATTACHMENT_QUERY :", attachment.name, attachment.hash)

                connection.commit()
        except Exception as error:
            connection.rollback()
            print(error)
    cur.close()


def get_seg():
    from sys import argv

    if len(argv) < 2:
        exit(0)

    x = int(argv[1])

    size = 3
    start, end = (x - 1) * size, min(x * size, len(boards))

    return [boards[b] for b in range(start, end)]


if __name__ == "__main__":
    # execute only if run as a script
    _boards = get_seg()
    for i in _boards:
        print(i.name)

    from timer import timer
    with timer():
        LIST_SIZE = 60

        articles = []
        bus_articles = []
        new_articles = []

        connection = connect_db()
        login_cookie = login()
        for board in _boards:
            board_articles = (
                crawling_job(board, page_size=ceil(LIST_SIZE / 10))
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

        if bus_articles:
            notice_to_slack(bus_articles)

        if new_articles:
            token = get_jwt_token()
            api_url = BATCH_CONFIG['notification_api_url']

            payload = {
                'update_notification': []
            }

            for article in new_articles:
                payload['update_notification'].append(article.id)

            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            requests.post(api_url, json=payload, headers=headers)

        connection.close()

