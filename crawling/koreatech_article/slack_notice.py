import json
import re
import config
import requests

import urllib3
import pymysql


COOP_BUSINESS_HOURS_TITLE_PATTERN = re.compile(
    r"^(?=.*(?:생협|생활협동조합))"
    r"(?=.*사업장\s*운영시간\s*안내)"
    r"(?=.*(?:\d{2,4}(?:학년도)?\s*[-.]?\s*[12]학기|(?:하계|동계)\s*방학)).*$"
)

BUS_TIMETABLE_TITLE_PATTERN = re.compile(
    r"^(?=.*(?:통학|셔틀).*?버스)"
    r"(?=.*운행(?:계획)?\s*(?:안내|알림))"
    r"(?=.*(?:20\d{2}학년도\s*[12]학기|"
    r"(?:20\d{2}(?:학년도|년)?\s*)?(?:하계|동계)\s*"
    r"(?:계절학기\s*[,·]?\s*)?방학(?:\s*기간)?)).*$"
)

LECTURE_REGISTRATION_TITLE_PATTERN = re.compile(
    r"^(?:"
    r"\[수강신청\]\s*20\d{2}학년도\s*[12]학기\s*"
    r"(?:(?:정규|예비)\s*)?수강신청\s*안내"
    r"|\[계절학기\]\s*20\d{2}학년도\s*(?:하계|동계)\s*"
    r"계절학기\s*(?:\d+차\s*)?수강신청\s*안내"
    r").*$"
)


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.MYSQL_CONFIG['host'],
                           port=config.MYSQL_CONFIG['port'],
                           user=config.MYSQL_CONFIG['user'],
                           password=config.MYSQL_CONFIG['password'],
                           db=config.MYSQL_CONFIG['db'],
                           charset='utf8')
    return conn


def filter_nas(connection, nas, keywords=None, exclude_keywords=None, title_pattern=None):

    articles = tuple(nas)

    # 키워드가 포함되었으며, 제외 키워드가 포함되지 않은 게시글 필터링
    if title_pattern:
        articles = (a for a in articles if title_pattern.search(a.title))
    elif keywords:
        if exclude_keywords:
            articles = (
                a for a in nas
                if any(keyword in a.title for keyword in keywords) and not any(word in a.title for word in exclude_keywords)
            )
        else:
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
        header = {'Content-type': 'application/json'}

        print(body)

        # 메세지 전송
        return requests.post(config.SLACK_CONFIG["url"], headers=header, json=body)

    except Exception as e:
        print("Slack Message 전송에 실패했습니다.")
        print("에러 내용 : ")
        print(e)


def notice_to_slack(articles, notice_type):
    notice_functions = {
        "bus": notice_bus_update,
        "coop": notice_coop_update,
        "lecture": notice_lecture_update,
    }

    for article in articles:
        notice_functions[notice_type](article.id)


def notice_article_update(article_id, notice_name, action_prefix):
    article_url = f"https://koreatech.in/articles/{article_id}"
    body = {
        "text": (
            f"{notice_name} 공지가 올라왔어요. 게시글 링크: {article_url}\n"
            "업데이트 작업을 진행할까요?"
        ),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{notice_name} 공지가 올라왔어요. "
                        f"<{article_url}|게시글 링크>\n"
                        "업데이트 작업을 진행할까요?"
                    )
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "예",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": f"{action_prefix}:detected",
                        "value": json.dumps({"article_id": article_id})
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "아니요",
                            "emoji": True
                        },
                        "action_id": f"{action_prefix}:detected_ignore",
                        "value": json.dumps({"article_id": article_id})
                    }
                ]
            }
        ]
    }

    response = send_message(body)
    if response is None:
        raise RuntimeError("Slack 메시지를 전송하지 못했습니다.")

    response.raise_for_status()
    return response

def notice_bus_update(article_id):
    return notice_article_update(article_id, notice_name="버스", action_prefix="bus")


def notice_lecture_update(article_id):
    return notice_article_update(article_id, notice_name="강의", action_prefix="lecture")


def notice_coop_update(article_id):
    return notice_article_update(article_id, notice_name="생협", action_prefix="coop")
