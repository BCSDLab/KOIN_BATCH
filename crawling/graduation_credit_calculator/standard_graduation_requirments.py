import pdfplumber
import logging
from sqlalchemy import create_engine, text

# 로그 설정
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

YEAR = [2019, 2020, 2021, 2022, 2023, 2024]
SEARCH_KEYWORD = "필요한 학점의 구성 및 배점(내국인용)"

# 학부별 전공 리스트
DEPARTMENT_MAJOR_MAP = {
    "기계공학부": [],
    "메카트로닉스공학부": ["생산시스템", "제어시스템", "디지털시스템"],
    "전기전자통신공학부": ["전기", "전자", "정보통신"],
    "컴퓨터공학부": [],
    "디자인건축공학부": ["디자인", "건축"],
    "에너지신소재화학공학부": ["에너지신소재", "응용화학"],
    "산업경영학부": ["산업경영", "혁신경영"],
}


def extract_table_from_pdf(pdf_path):
    """PDF에서 특정 키워드가 포함된 테이블을 찾아 추출"""
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            if text and SEARCH_KEYWORD in text:
                logging.info(f"🔍 [DEBUG] '{SEARCH_KEYWORD}' 키워드를 포함하는 페이지 발견: {page_num} 페이지")

                tables = page.extract_table()
                if tables:
                    first_row = tables[0]
                    second_row = tables[1] if len(tables) > 1 else []

                    category_indices = {}
                    for i, header in enumerate(first_row):
                        if header is None:
                            continue

                        header_cleaned = header.replace(" ", "").replace("\n", "")

                        if "교양" in header_cleaned:
                            category_indices["교양필수"] = i
                        if "HRD" in header_cleaned:
                            category_indices["HRD필수"] = i
                            category_indices["HRD선택"] = i + 1
                        if "전공" in header_cleaned:
                            category_indices["전공필수"] = i + 1  # 두 번째 칸
                            category_indices["전공선택"] = i + 2  # 세 번째 칸
                        if "자유선택" in header_cleaned:
                            category_indices["자유선택"] = i

                    first_row_cleaned = ["".join(cell.split()) if cell else None for cell in first_row]

                    if "MSC" in first_row_cleaned:
                        category_indices["MSC필수"] = first_row_cleaned.index("MSC")
                    else:
                        for i in range(len(second_row)):
                            if second_row[i]:
                                second_row_cleaned = second_row[i].replace(" ", "").replace("\n", "")
                                if "MSC" in second_row_cleaned:
                                    category_indices["MSC필수"] = i
                                    break
                                elif "수리적사고" in second_row_cleaned:
                                    category_indices["수리적사고"] = i
                                    break

                    logging.info(f"📝 [CATEGORY] 추출된 카테고리 인덱스: {category_indices}")
                    return tables[2:], category_indices

        logging.error(f"⚠️ PDF에서 '{SEARCH_KEYWORD}' 키워드를 포함하는 테이블을 찾을 수 없습니다.")
        return [], {}


def process_row(row, year, department_id, major_id, category_indices, conn):
    """한 개의 row 데이터를 데이터베이스에 저장할 수 있도록 변환"""
    insert_data = []

    for category, idx in category_indices.items():
        if idx is not None and idx < len(row) and row[idx] and str(row[idx]).isdigit():
            course_type_id = get_course_type_id(category, conn)
            if course_type_id is None:
                logging.warning(f"⚠️ [WARNING] {category}에 해당하는 course_type_id를 찾을 수 없음")
                continue

            if exists_in_db(year, department_id, major_id, course_type_id, conn):
                continue  # 중복 방지를 위해 저장하지 않음

            insert_data.append((year, department_id, major_id, course_type_id, int(row[idx])))

    return insert_data


def get_department_id(department_name, conn):
    """학부 이름을 받아 department 테이블에서 id 조회"""
    result = conn.execute(
        text("SELECT id FROM department WHERE name = :name"),
        {"name": department_name}
    ).fetchone()

    return result[0] if result else None


def get_major_id(major_name, department_id, conn):
    """전공 이름을 받아 major 테이블에서 id 조회"""
    result = conn.execute(
        text("SELECT id FROM major WHERE name = :name AND department_id = :dept_id"),
        {"name": major_name, "dept_id": department_id}
    ).fetchone()

    return result[0] if result else None


def get_course_type_id(course_type_name, conn):
    """교과 유형(course_type) ID 조회"""
    result = conn.execute(
        text("SELECT id FROM course_type WHERE name = :name"),
        {"name": course_type_name}
    ).fetchone()
    return result[0] if result else None


def exists_in_db(year, department_id, major_id, course_type_id, conn):
    """중복 데이터 확인"""
    result = conn.execute(
        text("""
            SELECT EXISTS (
                SELECT 1 FROM standard_graduation_requirements 
                WHERE year = :year 
                AND department_id = :dept_id 
                AND major_id <=> :major_id
                AND course_type_id = :course_type_id
            )
        """),
        {"year": year, "dept_id": department_id, "major_id": major_id, "course_type_id": course_type_id}
    ).fetchone()
    return result[0] == 1


def extract_and_insert_data(pdf_path, year, engine):
    with engine.connect() as conn:
        transaction = conn.begin()

        data_rows, category_indices = extract_table_from_pdf(pdf_path)

        row_index = 0

        # 🔹 2022년 이상부터 "고용서비스정책학과" 추가
        if int(year) >= 2022:
            department_id = get_department_id("고용서비스정책학과", conn)
            if department_id:
                insert_data = process_row(data_rows[row_index], year, department_id, None, category_indices, conn)
                if insert_data:
                    logging.info(f"📝 [{year}] {len(insert_data)}개 데이터 삽입 (학부: 고용서비스정책학과, 전공 없음)")
                    conn.execute(
                        text("""
                            INSERT INTO standard_graduation_requirements 
                            (year, department_id, major_id, course_type_id, required_grades) 
                            VALUES (:year, :dept, :major, :course, :required_grades)
                        """),
                        [{"year": y, "dept": d, "major": m, "course": c, "required_grades": s} for y, d, m, c, s in insert_data]
                    )

        for department_name, majors in DEPARTMENT_MAJOR_MAP.items():
            # 디자인건축공학부 예외 처리
            if department_name == "디자인건축공학부":
                department_ids = {
                    "디자인": get_department_id("디자인공학부", conn),
                    "건축": get_department_id("건축공학부", conn)
                }
            else:
                department_id = get_department_id(department_name, conn)

            if not majors:
                if row_index >= len(data_rows):
                    continue
                row = data_rows[row_index]
                insert_data = process_row(row, year, department_id, None, category_indices, conn)
                if insert_data:
                    logging.info(f"📝 [{year}] {len(insert_data)}개 데이터 삽입 (학부: {department_name}, 전공 없음)")
                    conn.execute(
                        text("""
                            INSERT INTO standard_graduation_requirements 
                            (year, department_id, major_id, course_type_id, required_grades) 
                            VALUES (:year, :dept, :major, :course, :required_grades)
                        """),
                        [{"year": y, "dept": d, "major": m, "course": c, "required_grades": s} for y, d, m, c, s in insert_data]
                    )
                row_index += 1
                continue

            for major in majors:
                while row_index < len(data_rows):
                    row = data_rows[row_index]
                    row_major = row[1].strip() if len(row) > 1 and row[1] else None

                    if row_major and any(m in row_major for m in majors):
                        if department_name == "디자인건축공학부":
                            department_id = department_ids.get(major)
                        major_id = get_major_id(major, department_id, conn)

                        insert_data = process_row(row, year, department_id, major_id, category_indices, conn)
                        if insert_data:
                            logging.info(f"📝 [{year}] {len(insert_data)}개 데이터 삽입 (학부: {department_name}, 전공: {major})")
                            conn.execute(
                                text("""
                                    INSERT INTO standard_graduation_requirements 
                                    (year, department_id, major_id, course_type_id, required_grades) 
                                    VALUES (:year, :dept, :major, :course, :required_grades)
                                """),
                                [{"year": y, "dept": d, "major": m, "course": c, "required_grades": s} for y, d, m, c, s in insert_data]
                            )
                        row_index += 1
                        break
                    row_index += 1

        transaction.commit()

if __name__ == "__main__":
    engine = create_engine("mysql+pymysql://root:ekhee0311!@localhost/koin")
    logging.info("📡 데이터베이스 연결 성공.")
    for year in YEAR:
        pdf_path = f"./pdfs/{year}대학요람.pdf"
        extract_and_insert_data(pdf_path, str(year), engine)
    logging.info("🎉 모든 데이터 삽입 완료.")
