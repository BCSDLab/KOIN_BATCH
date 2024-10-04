import config
import requests
from datetime import date

import urllib3
import pymysql


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.MYSQL_CONFIG['host'],
                           port=config.MYSQL_CONFIG['port'],
                           user=config.MYSQL_CONFIG['user'],
                           password=config.MYSQL_CONFIG['password'],
                           db=config.MYSQL_CONFIG['db'],
                           charset='utf8')
    return conn


def filter_nas(connection, nas, keywords=None):

    articles = tuple(nas)

    # 키워드가 포함된 게시글 필터링
    if keywords:
        articles = (a for a in nas for keyword in keywords if keyword in a.title)

    need_notice = []
    sql = f"SELECT COUNT(*) FROM koin.new_koreatech_articles ka JOIN koin.new_articles a on ka.article_id = a.id WHERE a.board_id = %s AND ka.portal_num = %s"
    with connection.cursor() as cursor:
        for article in articles:
            cursor.execute(sql % (article.board_id, article.num))
            result = cursor.fetchone()

            if result[0] == 0:
                need_notice.append(article)

    return need_notice


def send_message(body):
    try:
        url = config.SLACK_CONFIG["url"]
        header = {'Content-type': 'application/json'}

        print(body)

        # 메세지 전송
        return requests.post(url, headers=header, json=body)

    except Exception as e:
        print("Slack Message 전송에 실패했습니다.")
        print("에러 내용 : ")
        print(e)


def notice_to_slack(articles):
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "버스 공지 :Bus:",
                "emoji": True
            }
        },
        {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_list",
                    "style": "bullet",
                    "elements": []
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": f"업데이트: {date.today()}",
                    "emoji": True
                }
            ]
        }
    ]

    for art in articles:
        section = {
            "type": "rich_text_section",
            "elements": [
                {
                    "type": "link",
                    "url": art.url,
                    "text": art.title
                }
            ]
        }

        blocks[1]["elements"][0]["elements"].append(section)

    send_message({"blocks": blocks})
