import pymysql
import urllib3
import bs4
import enum
import config

articleBoard = {
    1: 5,
    2: 6,
    5: 0,
    6: 1,
    7: 2,
    8: 3,
    9: 4,
    10: 8
}


class ServiceType(enum.Enum):
    ANONYMOUS = 7
    LOST = 9
    MARKET = 10


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8', cursorclass=pymysql.cursors.DictCursor)
    return conn


def articlesMigration():
    cur = connection.cursor()
    cur.execute("SELECT * FROM koin.articles")

    rows = cur.fetchall()
    for row in rows:
        table_id = row['board_id']
        if table_id not in articleBoard:  # 레거시 게시판이면 스킵
            continue
        table_id = articleBoard[table_id]
        article_id = row['id']
        title = str(row['title'])
        content = row['content']
        user_id = row['user_id']
        nickname = str(row['nickname'])
        is_deleted = row['is_deleted']
        created_at = row['created_at']
        updated_at = row['updated_at']

        soup = bs4.BeautifulSoup(content if content is not None else "", features="html.parser")
        content = soup.text.strip()
        searchArticles = SearchArticlesMinified(table_id=table_id, article_id=article_id, title=title, content=content,
                                                user_id=user_id, nickname=nickname, is_deleted=is_deleted,
                                                created_at=created_at, updated_at=updated_at)

        updateDB(searchArticles)
    pass


def tempArticlesMigration():
    cur = connection.cursor()
    cur.execute("SELECT * FROM koin.temp_articles")

    rows = cur.fetchall()
    for row in rows:
        table_id = ServiceType.ANONYMOUS.value
        article_id = row['id']
        title = str(row['title'])
        content = str(row['content'])
        nickname = str(row['nickname'])
        is_deleted = row['is_deleted']
        created_at = row['created_at']
        updated_at = row['updated_at']

        soup = bs4.BeautifulSoup(content if content is not None else "", features="html.parser")
        content = soup.text.strip()
        searchArticles = SearchArticlesMinified(table_id=table_id, article_id=article_id, title=title, content=content,
                                                user_id=None, nickname=nickname, is_deleted=is_deleted,
                                                created_at=created_at, updated_at=updated_at)
        updateDB(searchArticles)
    pass


def lostItemsMigration():
    cur = connection.cursor()
    cur.execute("SELECT * FROM koin.lost_items")

    rows = cur.fetchall()
    for row in rows:
        table_id = ServiceType.LOST.value
        article_id = row['id']
        title = str(row['title'])
        content = str(row['content'])
        user_id = row['user_id']
        nickname = str(row['nickname'])
        is_deleted = row['is_deleted']
        created_at = row['created_at']
        updated_at = row['updated_at']

        soup = bs4.BeautifulSoup(content if content is not None else "", features="html.parser")
        content = soup.text.strip()
        searchArticles = SearchArticlesMinified(table_id=table_id, article_id=article_id, title=title, content=content,
                                                user_id=user_id, nickname=nickname, is_deleted=is_deleted,
                                                created_at=created_at, updated_at=updated_at)
        updateDB(searchArticles)
    pass


def itemsMigration():
    cur = connection.cursor()
    cur.execute("SELECT * FROM koin.items")

    rows = cur.fetchall()
    for row in rows:
        table_id = ServiceType.MARKET.value
        article_id = row['id']
        title = str(row['title'])
        content = str(row['content'])
        user_id = row['user_id']
        nickname = str(row['nickname'])
        is_deleted = row['is_deleted']
        created_at = row['created_at']
        updated_at = row['updated_at']

        soup = bs4.BeautifulSoup(content if content is not None else "", features="html.parser")
        content = soup.text.strip()
        searchArticles = SearchArticlesMinified(table_id=table_id, article_id=article_id, title=title, content=content,
                                                user_id=user_id, nickname=nickname, is_deleted=is_deleted,
                                                created_at=created_at, updated_at=updated_at)
        updateDB(searchArticles)
    pass


def updateDB(searchArticles):
    cur = connection.cursor()
    try:
        sql = """
        INSERT INTO koin.search_articles (table_id, article_id, title, content, user_id, nickname, is_deleted)
        VALUES ('%s', '%s', '%s', '%s', %s, '%s', '%s')
        ON DUPLICATE KEY UPDATE table_id = '%s', article_id = '%s'
        """

        searchArticles.title = searchArticles.title.replace("\\", "\\\\").replace("'", "\\'")
        searchArticles.content = searchArticles.content.replace("\\", "\\\\").replace("'", "\\'")

        cur.execute(sql % (
            searchArticles.table_id, searchArticles.article_id, searchArticles.title, searchArticles.content,
            searchArticles.user_id, searchArticles.nickname, searchArticles.is_deleted, searchArticles.table_id,
            searchArticles.article_id))

        connection.commit()

    except Exception as error:
        connection.rollback()
        print(error)
        print(searchArticles.__str__())


class SearchArticlesMinified:
    def __init__(self, table_id, article_id, title, content, user_id, nickname, is_deleted, created_at, updated_at):
        self.table_id = table_id
        self.article_id = article_id
        self.title = title
        self.content = content
        self.user_id = user_id if user_id is not None else 'NULL'
        self.nickname = nickname
        self.is_deleted = is_deleted
        self.created_at = created_at
        self.updated_at = updated_at
        pass

    def __str__(self):
        return "SearchArticles{" + \
               "table_id='" + str(self.table_id) + '\'' + \
               ", article_id='" + str(self.article_id) + '\'' + \
               ", title='" + str(self.title) + '\'' + \
               ", content='" + str(self.content) + '\'' + \
               ", user_id='" + str(self.user_id) + '\'' + \
               ", nickname='" + str(self.nickname) + '\'' + \
               ", is_deleted='" + str(self.is_deleted) + '\'' + \
               ", created_at='" + str(self.created_at) + '\'' + \
               ", updated_at='" + str(self.updated_at) + '\'' + \
               "}"


if __name__ == "__main__":
    connection = connect_db()
    articlesMigration()
    tempArticlesMigration()
    lostItemsMigration()
    itemsMigration()
    connection.close()
