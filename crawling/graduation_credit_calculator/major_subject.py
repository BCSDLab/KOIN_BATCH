import re
import pdfplumber
import pandas as pd
from sqlalchemy import create_engine, text
import logging
import config

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 연도별 SHAPE 설정 (지난 연도는 주석 처리 해야함)
YEARLY_SHAPES = {
    2019: "▶",
    2020: "❑",
    2021: "❑",
    2022: "❑",
    2023: "❑",
    2024: "❑"
}

# 연도별 키워드 설정 (지난 연도는 주석 처리 해야함)
YEARLY_KEYWORDS = {
    2019: [
        "융합학과", "기계공학부", "메카트로닉스공학부 생산시스템전공", "메카트로닉스공학부 제어시스템전공", "메카트로닉스공학부 디지털시스템전공",
        "전기・전자・통신공학부 전기공학전공", "전기・전자・통신공학부 전자공학전공", "전기・전자・통신공학부 정보통신공학전공",
        "컴퓨터공학부", "디자인・건축공학부 디자인공학전공", "디자인・건축공학부 건축공학전공",
        "에너지신소재화학공학부 에너지신소재공학전공", "에너지신소재화학공학부 응용화학공학전공", "산업경영학부 산업경영전공", "산업경영학부 혁신경영전공"
    ],
    2020: [
        "융합학과", "기계공학부", "메카트로닉스공학부 생산시스템전공", "메카트로닉스공학부 제어시스템전공", "메카트로닉스공학부 디지털시스템전공",
        "전기・전자・통신공학부 전기공학전공", "전기・전자・통신공학부 전자공학전공", "전기・전자・통신공학부 정보통신공학전공",
        "컴퓨터공학부", "디자인・건축공학부 디자인공학전공", "디자인・건축공학부 건축공학전공",
        "에너지신소재화학공학부 에너지신소재공학전공", "에너지신소재화학공학부 응용화학공학전공", "산업경영학부 산업경영전공", "산업경영학부 혁신경영전공"
    ],
    2021: [
        "융합학과", "기계공학부", "메카트로닉스공학부 생산시스템전공", "메카트로닉스공학부 제어시스템전공", "메카트로닉스공학부 디지털시스템전공",
        "전기・전자・통신공학부 전기공학전공", "전기・전자・통신공학부 전자공학전공", "전기・전자・통신공학부 정보통신공학전공",
        "컴퓨터공학부", "디자인・건축공학부 디자인공학전공", "디자인・건축공학부 건축공학전공",
        "에너지신소재화학공학부 에너지신소재공학전공", "에너지신소재화학공학부 응용화학공학전공", "산업경영학부"
    ],
    2022: [
        "융합학과", "기계공학부", "메카트로닉스공학부 생산시스템전공", "메카트로닉스공학부 제어시스템전공", "메카트로닉스공학부 디지털시스템전공",
        "전기・전자・통신공학부 전기공학전공", "전기・전자・통신공학부 전자공학전공", "전기・전자・통신공학부 정보통신공학전공",
        "컴퓨터공학부", "디자인・건축공학부 디자인공학전공", "디자인・건축공학부 건축공학전공",
        "에너지신소재화학공학부 에너지신소재공학전공", "에너지신소재화학공학부 응용화학공학전공", "산업경영학부", "데이터경영전공", "고용서비스정책학과"
    ],
    2023: [
        "융합학과 스페셜트랙", "기계공학부", "메카트로닉스공학부 생산시스템전공", "메카트로닉스공학부 제어시스템전공", "메카트로닉스공학부 디지털시스템전공",
        "전기・전자・통신공학부 전기공학전공", "전기・전자・통신공학부 전자공학전공", "전기・전자・통신공학부 정보통신공학전공",
        "컴퓨터공학부", "디자인・건축공학부 디자인공학전공", "디자인・건축공학부 건축공학전공",
        "에너지신소재화학공학부 에너지신소재공학전공", "에너지신소재화학공학부 응용화학공학전공", "융합경영전공", "데이터경영전공", "고용서비스정책학과"
    ],
    2024: [
        "융합학과 스페셜트랙", "기계공학부", "메카트로닉스공학부 생산시스템전공", "메카트로닉스공학부 제어시스템전공", "메카트로닉스공학부 디지털시스템전공",
        "전기・전자・통신공학부 전기공학전공", "전기・전자・통신공학부 전자공학전공", "전기・전자・통신공학부 정보통신공학전공",
        "컴퓨터공학부", "디자인・건축공학부 디자인공학전공", "디자인・건축공학부 건축공학전공",
        "에너지신소재화학공학부 에너지신소재공학전공", "에너지신소재화학공학부-화학생명공학전공", "융합경영전공", "데이터경영전공", "고용서비스정책학과"
    ]
}


# 표 헤더 (모든 연도에 대해 동일하게 유지)
TARGET_HEADER = ["교과목코드", "교과목명", "학-강-실-설", "이수구분"]


def is_similar_header(cleaned_header, target_header):
    def matches_target(cleaned_col, target_col):
        return target_col in cleaned_col

    for target_col in target_header:
        if not any(matches_target(cleaned_col, target_col) for cleaned_col in cleaned_header):
            return False
    return True


def clean_header(header):
    return [col.replace("\n", "").strip() for col in header if col and col.strip()]

def normalize_text(text):
    if not text:
        return ""
    normalized_text = re.sub(r"[・･·]", "・", text)
    normalized_text = normalized_text.replace("・", "")
    normalized_text = re.sub(r"\s+", "", normalized_text)
    return normalized_text.strip()

def extract_and_merge_tables(pdf_path, keyword):
    merged_table = []
    is_table_continued = False
    found_table_for_keyword = False

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue

                cleaned_text = normalize_text(text)
                shape = YEARLY_SHAPES.get(year, "")
                cleaned_keyword = f"{shape}{normalize_text(keyword)}"


                if cleaned_keyword in cleaned_text or is_table_continued:
                    logging.info(f"키워드 '{cleaned_keyword}'를 페이지 {i + 1}에서 찾았습니다.")

                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            if not table:
                                continue

                            current_header = clean_header(table[0])
                            current_header = [col for col in current_header if col]

                            if is_similar_header(current_header, TARGET_HEADER):
                                if not found_table_for_keyword:
                                    found_table_for_keyword = True
                                    is_table_continued = True

                                for row in table[1:]:
                                    filtered_row = row[:len(TARGET_HEADER)] + [None] * (len(TARGET_HEADER) - len(row))
                                    merged_table.append(filtered_row)

                            else:
                                if found_table_for_keyword:
                                    logging.info(f"새로운 표가 감지됨 (페이지 {i + 1}). 다음 키워드로 이동.")
                                    return merged_table

    except Exception as e:
        logging.error(f"PDF 처리 중 오류 발생: {e}")

    if not merged_table:
        logging.warning("병합된 테이블이 없습니다.")
        return None
    else:
        logging.info(f"총 {len(merged_table)}개의 데이터가 병합되었습니다.")
        return merged_table

def process_table_data(merged_table):
    try:
        if not merged_table:
            raise ValueError("유효하지 않은 테이블 데이터입니다.")

        df = pd.DataFrame(merged_table, columns=TARGET_HEADER)
        df.dropna(subset=["교과목코드", "교과목명"], inplace=True)

        df['credit'] = df['학-강-실-설'].apply(lambda x: int(x.split('-')[0]) if x and '-' in x else 0)

        logging.info(f"DataFrame 생성 완료. 총 {len(df)}개의 레코드가 처리되었습니다.")
        return df
    except Exception as e:
        logging.error(f"데이터 처리 중 오류 발생: {e}")
        raise

def create_engine_connection():
    try:
        db_config = config.DATABASE_CONFIG

        engine = create_engine(
            f"mysql+pymysql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['db']}"
        )
        logging.info("데이터베이스 연결 성공.")
        return engine
    except Exception as e:
        logging.error(f"데이터베이스 연결 실패: {e}")
        raise

def get_department_and_major(keyword, conn):
    normalized_keyword = re.sub(r"[・･·]", "・", keyword)
    normalized_keyword = normalized_keyword.replace("・", "").replace("-", " ")

    major_name = None

    if "디자인공학전공" in normalized_keyword:
        department_name = "디자인공학부"
        major_name = f"{department_name} 디자인공학전공"
    elif "건축공학전공" in normalized_keyword:
        department_name = "건축공학부"
        major_name = f"{department_name} 건축공학전공"
    elif "데이터경영전공" in normalized_keyword or "융합경영전공" in normalized_keyword:
        department_name = "산업경영학부"
        major_name = f"{department_name} {normalized_keyword}"
    elif normalized_keyword == "컴퓨터공학부":
        department_name = normalized_keyword
        major_name = f"{department_name} 컴퓨터공학전공"
    elif normalized_keyword == "기계공학부":
        department_name = normalized_keyword
        major_name = f"{department_name} 기계공학전공"
    elif normalized_keyword == "고용서비스정책학과":
        department_name = normalized_keyword
        major_name = f"{department_name} 고용서비스정책전공"
    elif normalized_keyword.endswith(("학부", "학과")):
        department_name = normalized_keyword
        major_name = None
    else:
        parts = normalized_keyword.split(" ")
        if "전공" in parts[-1]:
            major_name = normalized_keyword
            department_name = " ".join(parts[:-1])
        else:
            department_name = normalized_keyword

    result = conn.execute(
        text("SELECT id FROM department WHERE name = :name"), {"name": department_name}
    ).fetchone()
    if result:
        department_id = result[0]
    else:
        conn.execute(text("INSERT INTO department (name) VALUES (:name)"), {"name": department_name})
        department_id = conn.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

    if not major_name:
        return department_id, None

    result = conn.execute(
        text("SELECT id FROM major WHERE name = :name"), {"name": major_name}
    ).fetchone()
    if result:
        return department_id, result[0]

    conn.execute(
        text("INSERT INTO major (name, department_id) VALUES (:name, :department_id)"),
        {"name": major_name, "department_id": department_id}
    )
    major_id = conn.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

    return department_id, major_id


def get_or_create_course_type_id(course_type_name, conn):
    if "필수" in course_type_name:
        course_type_name = "전공필수"
    elif "선택" in course_type_name:
        course_type_name = "전공선택"

    result = conn.execute(
        text("SELECT id FROM course_type WHERE name = :name"), {"name": course_type_name}
    ).fetchone()
    if result:
        return result[0]
    conn.execute(
        text("INSERT INTO course_type (name) VALUES (:name)"), {"name": course_type_name}
    )
    new_id = conn.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
    logging.info(f"'{course_type_name}' 새 course_type ID 생성: {new_id}")
    return new_id


def insert_data_to_db(df, engine, year, keyword):
    try:
        with (engine.begin() as conn):
            for _, row in df.iterrows():
                if not row["교과목코드"]:
                    continue

                department_id, major_id = get_department_and_major(keyword, conn)

                course_type_id = get_or_create_course_type_id(row["이수구분"], conn)

                conn.execute(
                    text(
                        """
                        INSERT INTO catalog (year, code, lecture_name, department_id, major_id, credit, course_type_id) 
                        VALUES (:year, :code, :lecture_name, :department_id, :major_id, :credit, :course_type_id)
                        """
                    ),
                    {
                        "year": year,
                        "code": row["교과목코드"],
                        "lecture_name": row["교과목명"],
                        "department_id": department_id,
                        "major_id": major_id,
                        "credit": row["credit"],
                        "course_type_id": course_type_id,
                    },
                )

    except Exception as e:
        logging.error(f"데이터베이스 삽입 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    engine = create_engine_connection()

    for year, keywords in YEARLY_KEYWORDS.items():
        pdf_path = f"./pdfs/{year}대학요람.pdf"

        for keyword in keywords:
            logging.info(f"--------- {year}년도 대학요람에서 {keyword} 탐색 시작 ---------")
            merged_table = extract_and_merge_tables(pdf_path, keyword)

            if merged_table:
                df = process_table_data(merged_table)
                insert_data_to_db(df, engine, year, keyword)

    logging.info("모든 데이터 삽입 완료.")
