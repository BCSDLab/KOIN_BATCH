import pymysql
import urllib3
import openpyxl
from openpyxl.utils.cell import column_index_from_string
import config
import time

### static field ###
# 정규 수강신청 엑셀파일
filename = 'lecture.xlsx'  # 읽어들일 엑셀파일명
start_row = 7  # 데이터가 시작하는 row
end_row = 755  # 데이터가 끝나는 row
year_col = 'A'  # 학년도 column
semester_col = 'B'  # 학기 column
code_col = 'C'  # 교과목코드 column
name_col = 'D'  # 교과목명 column
grades_col = 'F'  # 학점 column
class_number_col = 'I'  # 분반 column
regular_number_col = 'J'  # 수정정원 column
department_col = 'L'  # 개설학과 column
target_col = 'M'  # 대상학과 학년 전공 column
professor_col = 'BB'  # 교수 column
is_english_col = 'BJ'  # 영어강의여부 column
design_score_col = 'BO'  # 설계학점 column
is_elearning_col = 'BM'  # 이러닝여부 column
class_time_col = 'AP'  # 시간 column

day_to_index = {'월': '0', '화': '1', '수': '2', '목': '3', '금': '4', '토': '5', '일': '6'}


def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn


def crawling():
    wb = openpyxl.load_workbook(filename=filename)
    ws = wb.active
    lectures = []
    year = ws['%s%d' % (year_col, start_row)].value
    semester = ws['%s%d' % (semester_col, start_row)].value
    semester_date = '%s%s' % (year, semester.split('학기')[0])

    for row in range(start_row, end_row + 1):
        code = ws['%s%d' % (code_col, row)].value
        name = ws['%s%d' % (name_col, row)].value
        grades = ws['%s%d' % (grades_col, row)].value
        class_number = ws['%s%d' % (class_number_col, row)].value
        regular_number = ws['%s%d' % (regular_number_col, row)].value
        if not regular_number:
            regular_number = ''
        department = ws['%s%d' % (department_col, row)].value
        if not department:
            department = ''
        target = ws['%s%d' % (target_col, row)].value
        if target:  # None이 아니라면 target의 여백들 지워준다.
            target = str(target).strip()
        else:
            target = ''
        professor = ws['%s%d' % (professor_col, row)].value
        if not professor:
            professor = ''
        is_english = ws['%s%d' % (is_english_col, row)].value
        design_score = ws['%s%d' % (design_score_col, row)].value
        is_elearning = ws['%s%d' % (is_elearning_col, row)].value
        class_time = convert_classtime(ws=ws, row=row)
        lecture = Lecture(semester_date=semester_date, code=code, name=name, grades=grades, class_number=class_number,
                          regular_number=regular_number, department=department, target=target,
                          professor=professor, is_english=is_english, design_score=design_score,
                          is_elearning=is_elearning, class_time=class_time)
        lectures.append(lecture)

        # print(semester_date, code, name, grades, class_number, regular_number, department, target, professor,
        #       is_english, design_score, is_elearning, class_time)

    updateDB(lectures=lectures, semester_date=semester_date)
    pass


def convert_classtime(ws, row):
    start_index = column_index_from_string(class_time_col)
    class_time = []
    for column in range(start_index, start_index + 12):
        detail_time = ws.cell(row=row, column=column).value
        if not detail_time or not detail_time.strip():  # 빈 시간 제외
            continue
        day = detail_time.split('/')[0]
        time = detail_time.split('/')[1]
        if not day or not time:  # 누락된 시간 예외 처리
            continue
        try:
            result = "%s%02d" % (day_to_index.get(day, ''), 2 * (int(time[0:2]) - 1) + ord(time[2:3]) - ord('A'))
            class_time.append(int(result))
        except Exception as error:
            print(error)
    return class_time


def updateDB(lectures, semester_date):
    cur = connection.cursor()
    try:
        cur.execute("INSERT INTO koin.semester (SEMESTER) \
                        SELECT '%s' FROM DUAL \
                            WHERE NOT EXISTS (SELECT SEMESTER FROM koin.semester WHERE SEMESTER='%s')" % (semester_date, semester_date))

        cur.execute("DELETE FROM koin.lectures WHERE SEMESTER_DATE='%s'" % semester_date)

        for lecture in lectures:
                sql = "INSERT INTO koin.lectures(semester_date, code, name, grades, class, regular_number, department, target, professor, is_english, design_score, is_elearning, class_time) \
                        VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"

                cur.execute(sql % (
                    lecture.semester_date, lecture.code, lecture.name, lecture.grades, lecture.class_number,
                    lecture.regular_number, lecture.department, lecture.target, lecture.professor,
                    lecture.is_english, lecture.design_score, lecture.is_elearning, lecture.class_time))

        cur.execute("UPDATE koin.versions SET version = '%s_%d' WHERE type = 'timetable'" % (semester_date, int(time.time())))
        connection.commit()

    except Exception as error:
        connection.rollback()
        print(error)


class Lecture:
    def __init__(self, semester_date, code, name, grades, class_number, regular_number, department, target, professor,
                 is_english, design_score, is_elearning, class_time):
        self.semester_date = semester_date
        self.code = code
        self.name = name
        self.grades = grades
        self.class_number = class_number
        self.regular_number = regular_number
        self.department = department
        self.target = target
        self.professor = professor
        self.is_english = is_english
        self.design_score = design_score
        self.is_elearning = is_elearning
        self.class_time = class_time
        pass


if __name__ == "__main__":
    connection = connect_db()
    crawling()
    connection.close()
