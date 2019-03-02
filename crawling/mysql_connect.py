import pymysql

# cur = db.cursor()
# cur.execute("UPDATE member SET ip=''")
# db.commit()
# db.close()

class MysqlUtil:
    def __init__(self):
        self.db = pymysql.connect(host="localhost", user="root", passwd="qpqp1010", db="koin", charset='utf8')

    def update(self, query):
        cursor = self.db.cursor()
        cursor.execute(query)
        for row in cursor:
            print(row[0]);
    
    def commit(self):
        self.db.commit()
    
    def close(self):
        self.db.close()
        
MysqlUtil = MysqlUtil()
MysqlUtil.update("SELECT * FROM koin.users")