import pymysql
import config

# cur = db.cursor()
# cur.execute("UPDATE member SET ip=''")
# db.commit()
# db.close()

class MysqlUtil:
    def __init__(self):
        self.db = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                                  port=config.DATABASE_CONFIG['port'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')

    def update(self, query):
        cursor = self.db.cursor()
        cursor.execute(query)
        for row in cursor:
            print(row[0])
    
    def commit(self):
        self.db.commit()
    
    def close(self):
        self.db.close()
        
MysqlUtil = MysqlUtil()
MysqlUtil.update("SELECT * FROM koin.users")