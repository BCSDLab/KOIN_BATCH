import requests
from bs4 import BeautifulSoup


def make_sql(board_id, articles):
    sql = f'''
        SELECT na.id, nka.url
        FROM new_articles na
            JOIN new_koreatech_articles nka ON na.id = nka.article_id
        WHERE na.board_id = {board_id}
        AND na.is_delete = 0
        '''

    exists = ', '.join(str(article.id) for article in articles)
    if exists:
        sql += f'AND na.id NOT IN ({exists})\n'

    sql += 'ORDER BY na.id ASC LIMIT 60'

    return sql


def is_deleted(board_id, response):
    try:
        # 취업 공지가 아닌 경우
        if board_id != 8:
            return '/eXPortal/ctt/css/error.css' in response.text

        # 취업 공지
        if response.url == 'https://job.koreatech.ac.kr/ErrorPages/warning.html':
            return True

        html = BeautifulSoup(response.text, 'html.parser')

        # content가 비어있으면 삭제된 것이므로 이므로 True
        return not html.select_one('#content').text.strip()
    except Exception as e:
        print(e)
        return False


def delete_article(connection, board_id, articles, cookies):
    """
    is_deleted = 1인 게시글에 대해서는 판별하지 않음
    즉, 이미 지워졌다고 판별된 게시글에 대해서는 판별하지 않음

    articles에 들어있는 게시글은 존재하는 게시글이므로 판별하지 않음

    :param connection: mysql 커넥션
    :param board_id: DB boards에 들어있는 게시판 아이디: `boards.id`
    :param articles: 방금 막 크롤링한 따끈따끈한 게시글들
    :param cookies: 로그인 쿠키
    """
    sql = make_sql(board_id, articles)

    with connection.cursor() as cursor:
        cursor.execute(sql)
        rows = cursor.fetchall()

        deleted = []

        for article_id, url in rows:
            response = requests.get(url, cookies=cookies, timeout=5)
            if is_deleted(board_id, response):
                deleted.append(article_id)

        try:
            for article_id in deleted:
                sql = f'UPDATE new_articles SET is_deleted = 1 WHERE id = {article_id}'
                cursor.execute(sql)

                sql = f'UPDATE new_koreatech_articles SET is_deleted = 1 WHERE article_id = {article_id}'
                cursor.execute(sql)

                connection.commit()
                print("DELETE_QUERY :", article_id)

        except Exception as e:
            connection.rollback()
            print(e)
