import config
import requests
from datetime import date

import urllib3
import pymysql


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           port=config.DATABASE_CONFIG['port'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn


def filter_nas(connection, nas, keywords):

    # 키워드가 포함된 게시글 필터링
    articles = (a for a in nas for keyword in keywords if keyword in a.title)

    need_notice = []
    sql = f"SELECT COUNT(*) FROM koin.notice_articles WHERE board_id = %s AND article_num = %s"
    with connection.cursor() as cursor:
        for article in articles:
            cursor.execute(sql % (article.board_id, article.article_num))
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

        exit(0)


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
                    "url": art.permalink,
                    "text": art.title
                }
            ]
        }

        blocks[1]["elements"][0]["elements"].append(section)

    send_message({"blocks": blocks})
