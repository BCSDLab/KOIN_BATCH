import pymysql
import datetime
import config
from typing import List

def connect_db():
    db = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           port=config.DATABASE_CONFIG['port'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'])
    return db

def hard_delete_soft_deleted_data(db, table: str, days: int):
    with db.cursor() as cursor:
        threshold_date = datetime.datetime.now() - datetime.timedelta(days = days)
        sql = "DELETE FROM `{}` WHERE is_deleted = 1 AND updated_at < %s".format(table)
        cursor.execute(sql, (threshold_date,))
        db.commit()
        print(f"{cursor.rowcount} rows deleted from {table}")

def run_cleanup(tables: List[str], days = 60):
    db = connect_db()

    for table in tables:
        hard_delete_soft_deleted_data(db, table, days)

    db.close()

if __name__ == "__main__":
    target_tables = ["activities", "article_attachments", "boards", "new_articles", "comments", "koin_notice", "new_koin_articles",
               "new_koreatech_articles", "lost_item_articles", "lost_item_images", "course_type", "standard_graduation_requirements",
               "student_course_calculation", "lands", "members", "tracks", "tech_stacks", "owner_attachments", "event_articles",
               "shops", "shop_opens", "shop_reviews", "timetable_frame", "timetable_lecture", "users", "article_keywords",
               "article_keyword_user_map"]
    run_cleanup(target_tables, 60)
