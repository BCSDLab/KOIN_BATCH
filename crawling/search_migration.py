# NOTE : 추후 Python 3.6 이상을 쓰면 문자열 모두 f-string으로 변경할 것
# @Author : 정종우
# @Modified : 최선문 / 2020.04.29

import pymysql
import urllib3
import bs4
from enum import Enum
from config import DATABASE_CONFIG

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

# @Desc : 서비스 타입을 나타내는 열거형으로 koin table_id 값을 따른다.
class EServiceType(Enum):
    Anonymous = 7
    LostItem = 9
    Market = 10
    Event = 11

# @Desc : 이전할 스키마 타입이다. 각 값은 서비스 타입을 따른다.
class ESchemaType(Enum):
    # articles는 board_id를 이용해 값을 할당한다.
    articles = -1
    temp_articles = EServiceType.Anonymous.value
    lost_items = EServiceType.LostItem.value
    items = EServiceType.Market.value
    event_articles = EServiceType.Event.value

# @Desc : 검색용 아티클
class SearchArticle:
    def __init__(self, schemaType):
        self.schemaType = ESchemaType[schemaType]
        self.table_id = self.schemaType.value
        self.article_id = 0
        self.user_id = "NULL"
        self.__title = ""
        self.__content = ""
        self.nickname = "NULL"
        self.is_deleted = 0
        self.created_at = ""
        self.updated_at = ""

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

    @property
    def title(self):
        return self.__title

    @title.setter
    def title(self, value):
        self.__title = self.convertToDbString(value)

    @property
    def content(self):
        return self.__content

    @content.setter
    def content(self, value):
        self.__content =  self.convertToDbString(value)
    
    @staticmethod
    def convertToDbString(source):
        # HACK : DB에 제대로 저장되려면 아래와 같이 바꿔줘야 한다.
        return source.replace("\\", "\\\\").replace("'", "\\'")
       
# @Desc : DB와 연결한다.
def getConnectionToDB():
    # HACK : 혹시나 URL로 접속한다면 HTTPS 접속 때문에 오류가 생길 수 있다.
    # 그럴 때 이 코드를 활성화 하라.
    # urllib3.disable_warnings()

    conn = pymysql.connect(
        host = DATABASE_CONFIG['host'],
        user = DATABASE_CONFIG['user'],
        password = DATABASE_CONFIG['password'],
        db = DATABASE_CONFIG['db'],
        charset = 'utf8', cursorclass = pymysql.cursors.DictCursor)

    return conn

# @Author : 최선문
# @Return : SearchArticle
# @Param
# schemaType : ESchemaType에 들어있는 열거형 값의 name이다.
# row : DictCursor로 조회한 레코드다.
# @Desc : 스키마 타입과 행을 이용해서 SearchArticle 객체를 생성한다.
def makeSearchArticle(schemaType, row):
    searchArticle = SearchArticle(schemaType)

    # articles 스키마의 경우 table_id를 설정할 때 예외 처리를 해야 한다.
    if searchArticle.schemaType == ESchemaType.articles:
        if row["board_id"] not in articleBoard:
            return None
        searchArticle.table_id = articleBoard[row["board_id"]]
    # 그 외의 경우는 ESchemaType 값으로 넣는다.
    else:
        searchArticle.table_id = searchArticle.schemaType.value

    searchArticle.article_id = row["id"]
    searchArticle.user_id = row.get("user_id", "NULL")
    searchArticle.title = row["title"]
    searchArticle.nickname = row["nickname"]
    searchArticle.is_deleted = row["is_deleted"]
    searchArticle.created_at = row["created_at"]
    searchArticle.updated_at = row["updated_at"]
    content = row["content"] if row["content"] is not None else ""
    soup = bs4.BeautifulSoup(content, features = "html.parser")
    searchArticle.content = soup.text.strip()
    
    return searchArticle

# @Author : 최선문
# @Date : 2020.04.28
# @Param
# schemaType : ESchemaType에 들어있는 열거형의 name이다. 
# @Desc : 스키마에 있는 모든 컬럼을 가져와 search_articles로 이전한다.
def migrate(schemaType):
    COUNT = 5000

    # Row를 얻어 온다.
    id = 0
    while True:
        rows = []
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM koin.{} LIMIT {}, {}".format(schemaType, id, COUNT))
            rows = cursor.fetchall()
            size = len(rows)
            
            # 더 가져올 행이 없다면 다음 스키마를 조회한다.
            if size == 0:
                break

            print("[Log] Selected Row From {} to {} : {}".format(id, id + size, size))
            id += size

        # search_articles에 넣는다.
        count = 0
        for row in rows:
            searchArticle = makeSearchArticle(schemaType, row)
            if not searchArticle:
                continue
            updateDB(searchArticle)
            count += 1
            print("[Log] Current row : {}".format(count), end = "\r")
    print("\n[Log] Done")        

# @Param
# searchArticle : makeSearchArticle로 생성한 객체다.
# @Desc : search_articles로 해당 row를 insert 한다.
def updateDB(searchArticle):
    try:
        with connection.cursor() as cursor:
            # SQL문 생성
            sql = """
            INSERT INTO koin.search_articles (table_id, article_id, title, content, user_id, nickname, is_deleted, created_at, updated_at) VALUES ('%s', '%s', '%s', '%s', %s, '%s', '%s', '%s', '%s') ON DUPLICATE KEY UPDATE title = '%s', content = '%s', user_id = %s, nickname = '%s', is_deleted = '%s'
            """

            completedSQL = sql % (searchArticle.table_id, searchArticle.article_id, searchArticle.title, searchArticle.content, searchArticle.user_id, searchArticle.nickname, searchArticle.is_deleted, searchArticle.created_at, searchArticle.updated_at, searchArticle.title, searchArticle.content, searchArticle.user_id, searchArticle.nickname, searchArticle.is_deleted)

            # SQL 검증
            # print(completedSQL)

            # 질의 실행
            cursor.execute(completedSQL)

            # 커밋
            connection.commit()
    except Exception as error:
        print("[Error] Row : {}".format(searchArticle))
        raise error

if __name__ == "__main__":
    print("[Log] Migration Start")
    
    # DB 연결
    connection = getConnectionToDB()
    print("[Log] Connection Succeeded")
    
    # 스키마 이전
    try:
        for schema, value in ESchemaType.__members__.items():
            print("[Log] Start migrating {}".format(schema))
            migrate(schema)
    except Exception as error:
        connection.rollback()
        print("[Error] {}".format(error))
        print("[Log] Rollbacking...")
    finally:
        connection.close()
        print("[Log] Connection Closed")