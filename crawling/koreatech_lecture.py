import sys
import pymysql
import urllib3
import openpyxl
# from openpyxl.utils.cell import column_index_from_string
import config
import time
from datetime import date
from enum import Enum

sys.path.append("/home/ubuntu/myvenv/lib/python3.5/site-packages")

class ColumnNames(Enum):
    # 매핑이 되는 칼럼 명을 여러가지로 설정할 수 있도록 하였다.
    # `학\n점` 등으로 적혀져 있는 것을 주의할 것
    # 23.3 기준, 학교에서 "수강정원" 대신 "수정정원"으로 올려놓아서, 이에 대응하기 위해 설정하였다.
    SEMESTER = ["학기" ]
    CODE = ["과목코드" ]
    NAME = ["교과목명" ]
    GRADES = ["학\n점" ]
    CLASS_NUMBER = ["분반" ]
    REGULAR_NUMBER = ["수강\n정원", "수정\n정원"]
    DEPARTMENT = ["개설학부(과)" ]
    TARGET = ["수강신청\n가능학년" ]
    PROFESSOR = ["담당교수" ]
    IS_ENGLISH = ["영어강의" ]
    DESIGN_SCORE = ["설\n계" ]
    ## e러닝은 병합이 되어있지만 첫 열을 가져오도록 로직이 구성되어있다.
    IS_ELEARNING = ["E-Learning" ]
    CLASS_TIME = ["강의시간" ]

    def include(self, column_name):
        return column_name in self.value




### static field ###
# 정규 수강신청 엑셀파일
year = date.today().year  # 오늘 연도
filename = 'lecture.xlsx'  # 읽어들일 엑셀파일명
start_row = 5  # 데이터가 시작하는 row
end_row = 791  # 데이터가 끝나는 row
semester_col = 'D'  # 학기 column
code_col = 'E'  # 교과목코드 column
name_col = 'F'  # 교과목명 column
grades_col = 'J'  # 학점 column
class_number_col = 'G'  # 분반 column
regular_number_col = 'V'  # 수정정원 column
department_col = 'O'  # 개설학과 column
target_col = 'Q'  # 대상학과 학년 전공 column
professor_col = 'S'  # 교수 column
is_english_col = 'AI'  # 영어강의여부 column
design_score_col = 'M'  # 설계학점 column
is_elearning_col = 'AF'  # 이러닝여부 column
class_time_col = 'R'  # 시간 column

day_to_index = {'월': '0', '화': '1', '수': '2', '목': '3', '금': '4', '토': '5', '일': '6'}


class WorkSheetHelper:
    def __init__(self, work_sheet):
        self.sheet = work_sheet
        self.max_row = work_sheet.max_row
        self.max_column = work_sheet.max_column

        for i in range(1, self.max_row + 1):
            if self.at('A', i) == 'No.':
                self.schema_row = i
                self.instance_row = i + 1
                break

    # A1 형식으로 셀에 접근 (col, row 순)
    def at(self, column, row):
        return self.sheet['%s%d' % (column, row)].value


class ColumnMapping:
    def __init__(self, work_sheet_helper):
        self.mapping_table = {}

        row = work_sheet_helper.schema_row
        for i in range(1, work_sheet_helper.max_column + 1):
            col = self.get_column(i)

            self.mapping_for(col, row, work_sheet_helper)

        self.validates()

    def validates(self):
        if len(self.mapping_table) != len(ColumnNames):
            errors = ""

            for actual_column_name in self.mapping_table:
                for expected_column_name in ColumnNames:
                    if not expected_column_name.include(actual_column_name):
                        errors += "%s(%s) " % (expected_column_name.name, expected_column_name.value)

    def get_column(self, i):
        if i <= 26:
            return chr(i + 64)
        else:
            return chr(i // 26 + 64) + chr(i % 26 + 64)

    def mapping_for(self, col, row, work_sheet_helper):
        for column_name in ColumnNames:
            if column_name.include(work_sheet_helper.at(col, row)):
                self.mapping_table[column_name] = col
                break

    def get(self, column_name):
        return self.mapping_table[column_name]




def connect_db():
    urllib3.disable_warnings()
    conn = pymysql.connect(host=config.DATABASE_CONFIG['host'],
                           user=config.DATABASE_CONFIG['user'],
                           password=config.DATABASE_CONFIG['password'],
                           db=config.DATABASE_CONFIG['db'],
                           charset='utf8')
    return conn


def crawling():
    wb = openpyxl.load_workbook(filename=filename, data_only=True)
    ws = wb.active
    lectures = []
    semester = ws['%s%d' % (semester_col, start_row)].value
    semester_date = '%s%s' % (year, semester.split('학기')[0])
    work_sheet_helper = WorkSheetHelper(ws)
    column_mapping = ColumnMapping(work_sheet_helper)

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
        class_time = convert_classtime(ws['%s%d' % (class_time_col, row)].value)
        lecture = Lecture(semester_date=semester_date, code=code, name=name, grades=grades, class_number=class_number,
                          regular_number=regular_number, department=department, target=target,
                          professor=professor, is_english=is_english, design_score=design_score,
                          is_elearning=is_elearning, class_time=class_time)
        lectures.append(lecture)

        print(semester_date, code, name, grades, class_number, regular_number, department, target, professor,
              is_english, design_score, is_elearning, class_time)

    updateDB(lectures=lectures, semester_date=semester_date)
    pass


def convert_classtime(class_time):  # 강의 시간 변환 신버전
    classList = []
    day = ''
    try:
        for time in class_time.split(','):  # ,를 기준으로 파싱
            if time[0].isalpha():
                day = time[0]  # 요일
                time = time[1:]  # 요일을 제외한 강의 시간
            periodFlag = False
            period = time.split('~')  # ~를 기준으로 파싱
            timeTo = timeFrom = 0
            for p in period:
                result = "%s%02d" % (day_to_index.get(day, ''), 2 * (int(p[0:2]) - 1) + ord(p[2:3]) - ord('A'))  # 변환 공식
                if not periodFlag:
                    timeFrom = int(result)
                    periodFlag = True
                else:
                    timeTo = int(result)

            if not timeTo:  # timeTo가 할당되지 않은 예외 상황이라면
                timeTo = timeFrom  # 동일하게 할당

            for i in range(timeFrom, timeTo + 1):
                classList.append(i)
    except Exception:
        print('Error occured at: %s' % class_time)
        return []
    return classList


# def convert_classtime(ws, row):  # 강의 시간 변환 구버전

# start_index = column_index_from_string(class_time_col)
# class_time = []
# for column in range(start_index, start_index + 12):
#     detail_time = ws.cell(row=row, column=column).value
#     if not detail_time or not detail_time.strip():  # 빈 시간 제외
#         continue
#     day = detail_time.split('/')[0]
#     time = detail_time.split('/')[1]
#     if not day or not time:  # 누락된 시간 예외 처리
#         continue
#     try:
#         result = "%s%02d" % (day_to_index.get(day, ''), 2 * (int(time[0:2]) - 1) + ord(time[2:3]) - ord('A'))
#         class_time.append(int(result))
#     except Exception as error:
#         print(error)
# return class_time


def updateDB(lectures, semester_date):
    cur = connection.cursor()
    try:
        cur.execute("INSERT INTO koin.semester (SEMESTER) \
                        SELECT '%s' FROM DUAL \
                            WHERE NOT EXISTS (SELECT SEMESTER FROM koin.semester WHERE SEMESTER='%s')" % (
            semester_date, semester_date))

        cur.execute("DELETE FROM koin.lectures WHERE SEMESTER_DATE='%s'" % semester_date)

        for lecture in lectures:
            sql = "INSERT INTO koin.lectures(semester_date, code, name, grades, class, regular_number, department, target, professor, is_english, design_score, is_elearning, class_time) \
                        VALUES ('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')"

            cur.execute(sql % (
                lecture.semester_date, lecture.code, lecture.name, lecture.grades, lecture.class_number,
                lecture.regular_number, lecture.department, lecture.target, lecture.professor,
                lecture.is_english, lecture.design_score, lecture.is_elearning, lecture.class_time))

        cur.execute(
            "UPDATE koin.versions SET version = '%s_%d' WHERE type = 'timetable'" % (semester_date, int(time.time())))
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
