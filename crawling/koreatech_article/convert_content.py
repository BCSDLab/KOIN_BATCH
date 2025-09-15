import pymysql
import urllib3
import uuid

from config import MYSQL_CONFIG
from table import upload_txt


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=MYSQL_CONFIG['host'],
                           port=MYSQL_CONFIG['port'],
                           user=MYSQL_CONFIG['user'],
                           password=MYSQL_CONFIG['password'],
                           db=MYSQL_CONFIG['db'],
                           charset='utf8')
    return conn


def convert_content_to_url(connection):
    cur = connection.cursor()
    batch_size = 500
    last_id = 0
    total_articles = 0

    while True:
        try:
            cur.execute("""
                SELECT `id`, `board_id`, `content`
                FROM `new_articles`
                WHERE `content` IS NOT NULL
                    AND `board_id` != 14
                    AND `id` > %s
                ORDER BY `id` ASC
                LIMIT %s
            """, (last_id, batch_size))

            articles = cur.fetchall()
            if not articles:
                break

            for article in articles:
                article_id, board_id, content = article
                random_uuid = str(uuid.uuid4().hex)
                file_name = f'articles/content/board_{board_id}/{random_uuid}.txt'
                content_url = upload_txt(file_name=file_name, text_content=content)

                update_cur = connection.cursor()
                update_cur.execute("""
                    UPDATE `new_articles`
                    SET `content` = %s
                    WHERE `id` = %s
                """, (content_url, article_id))
                print(f"article {article_id} url: {content_url}")
                update_cur.close()

                total_articles += 1

            last_id = articles[-1]['id']

            connection.commit()

        except Exception as error:
            connection.rollback()
            print(error)
        finally:
            cur.close()
            print(f"total articles: {total_articles}")


if __name__ == "__main__":
    connection = None
    try:
        connection = connect_db()
        convert_content_to_url(connection)
    except Exception as error:
        print(error)
    finally:
        connection.close()
