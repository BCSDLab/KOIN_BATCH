import pdfplumber
import pandas as pd
from sqlalchemy import create_engine, text
import logging
import config

# 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 연도별 키워드 설정
YEARLY_KEYWORDS = {
    2019: ["가. 교양", "가. HRD학과", "나. MSC"],
    2020: ["❑ 교양 교과목표", "❑ HRD학과 교과목표", "❑ MSC 교과목표"],
    2021: ["❑ 교양 교과목표", "❑ HRD학과 교과목표", "❑ MSC 교과목표"],
    2022: ["❑ 교양 교과목", "❑ HRD학과 교과목", "❑ MSC 교과목"],
    2023: ["❑ 교양 교과목", "❑ HRD학과 교과목", "❑ MSC 교과목"],
    2024: ["❑ 교양 교과목", "❑ HRD학과 교과목", "❑ 수리적사고 교과목"],
}

# 표 헤더
TARGET_HEADER = ["교과목코드", "교과목명", "학-강-실-설", "이수구분"]

def is_similar_header(cleaned_header, target_header):
    def matches_target(cleaned_col, target_col):
        if target_col in ["학-강-실", "학-강-실-설"]:
            return "학-강-실" in cleaned_col or "학-강-실-설" in cleaned_col
        return target_col in cleaned_col

    for target_col in target_header:
        if not any(matches_target(cleaned_col, target_col) for cleaned_col in cleaned_header):
            return False
    return True

def clean_header(header):
    return [col.replace("\n", "").strip() for col in header if col and col.strip()]

def extract_and_merge_tables(pdf_path, keyword):
    merged_table = []
    header = None
    is_table_continued = False
    found_table_for_keyword = False
    final_target_header = TARGET_HEADER[:]

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                first_table = True
                cleaned_text = " ".join(text.split()) if text else ""
                cleaned_keyword = " ".join(keyword.split())

                if cleaned_keyword in cleaned_text or is_table_continued:
                    logging.info(f"키워드 '{keyword}'를 페이지 {i + 1}에서 찾음")

                    tables = page.extract_tables()
                    is_multiple_tables = len(tables) > 1

                    if tables:
                        for table in tables:
                            if table:
                                current_header = clean_header(table[0])

                                if is_similar_header(current_header, final_target_header):
                                    if "영역" in current_header and "영역" not in final_target_header:
                                        final_target_header.append("영역")

                                    if not header:
                                        header = current_header

                                    target_indices = [
                                        current_header.index(col)
                                        if col in current_header else current_header.index("학-강-실")
                                        for col in final_target_header
                                        if col in current_header or col == "학-강-실-설" and "학-강-실" in current_header
                                    ]

                                    filtered_table = [
                                        [row[idx] if idx < len(row) else None for idx in target_indices] for row in table[1:]
                                    ]
                                    merged_table.extend(filtered_table)
                                    found_table_for_keyword = True
                                    is_table_continued = True

                                    if first_table and is_multiple_tables:
                                        is_table_continued = False
                                    break

                                else:
                                    is_table_continued = False
                                    first_table = False

                    else:
                        is_table_continued = False

                if not is_table_continued and found_table_for_keyword:
                    break

    except Exception as e:
        logging.error(f"PDF 처리 중 오류 발생: {e}")

    return merged_table if merged_table else None, final_target_header

def process_table_data(merged_table, target_header):
    try:
        if not merged_table:
            raise ValueError("유효하지 않은 테이블 데이터")

        df = pd.DataFrame(merged_table, columns=target_header)
        df.dropna(subset=["교과목코드", "교과목명"], inplace=True)
        df['credit'] = df['학-강-실-설'].apply(lambda x: int(x.split('-')[0]) if x and '-' in x else 0)

        logging.info(f"DataFrame 생성 완료. {len(df)}개 레코드 처리")
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
        logging.info("데이터베이스 연결 성공")
        return engine
    except Exception as e:
        logging.error(f"데이터베이스 연결 실패: {e}")
        raise

def insert_data_to_db(df, engine, year):
    def get_or_create_department(conn):
        department_name = "공통 학부"
        result = conn.execute(text("SELECT id FROM department WHERE name = :name"), {"name": department_name}).fetchone()
        if result:
            return result[0]
        conn.execute(text("INSERT INTO department (name) VALUES (:name)"), {"name": department_name})
        return conn.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

    def get_or_create_course_type_id(course_type_name, conn):
        if not course_type_name.strip():
            return None
        if course_type_name == "중등교직":
            course_type_name = "자유선택"
        result = conn.execute(text("SELECT id FROM course_type WHERE name = :name"), {"name": course_type_name}).fetchone()
        if result:
            return result[0]
        conn.execute(text("INSERT INTO course_type (name) VALUES (:name)"), {"name": course_type_name})
        return conn.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

    def get_or_create_area_id(area_name, conn):
        if not area_name or not area_name.strip():
            return None
        result = conn.execute(text("SELECT id FROM general_education_area WHERE name = :name"), {"name": area_name}).fetchone()
        if result:
            return result[0]
        conn.execute(text("INSERT INTO general_education_area (name) VALUES (:name)"), {"name": area_name})
        return conn.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]

    def exists_in_general_education_area_map(year, course_type_id, area_id, conn):
        result = conn.execute(
            text("""
                SELECT 1 FROM general_education_area_course_type_map 
                WHERE year = :year AND course_type_id = :course_type_id 
                      AND general_education_area_id = :area_id
            """),
            {"year": year, "course_type_id": course_type_id, "area_id": area_id}
        ).fetchone()
        return result is not None

    try:
        with engine.begin() as conn:
            department_id = get_or_create_department(conn)

            for _, row in df.iterrows():
                area_id = get_or_create_area_id(row['영역'], conn) if "영역" in df.columns else None
                course_type_id = get_or_create_course_type_id(row['이수구분'], conn)

                conn.execute(
                    text("""
                        INSERT INTO catalog (year, code, lecture_name, department_id, credit, course_type_id) 
                        VALUES (:year, :code, :lecture_name, :department_id, :credit, :course_type_id)
                    """),
                    {"year": year, "code": row['교과목코드'], "lecture_name": row['교과목명'],
                     "department_id": department_id, "credit": row['credit'], "course_type_id": course_type_id}
                )

                if area_id and course_type_id and not exists_in_general_education_area_map(year, course_type_id, area_id, conn):
                    conn.execute(
                        text("""
                            INSERT INTO general_education_area_course_type_map (general_education_area_id, course_type_id, year) 
                            VALUES (:area_id, :course_type_id, :year)
                        """),
                        {"area_id": area_id, "course_type_id": course_type_id, "year": year}
                    )

    except Exception as e:
        logging.error(f"데이터베이스 삽입 중 오류 발생: {e}")
        raise

if __name__ == "__main__":
    engine = create_engine_connection()

    for year, keywords in YEARLY_KEYWORDS.items():
        logging.info(f"==== {year}년 데이터 처리 시작 ====")
        pdf_path = f"./pdfs/{year}대학요람.pdf"

        for keyword in keywords:
            logging.info(f"키워드 '{keyword}' 처리 중...")
            merged_table, final_target_header = extract_and_merge_tables(pdf_path, keyword)

            if merged_table:
                df = process_table_data(merged_table, final_target_header)
                insert_data_to_db(df, engine, year)

    logging.info("모든 데이터 삽입 완료.")