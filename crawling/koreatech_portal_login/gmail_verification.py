import imaplib
import email
import time
from email.header import decode_header
from email.utils import parsedate_to_datetime, parseaddr
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import config

# 설정 불러오기
gmail_id = config.GMAIL_CONFIG['id']
gmail_pw = config.GMAIL_CONFIG['pw']
from_email = "kutcc@koreatech.ac.kr" # 인증 메일 발송자 메일 주소
time_threshold = timedelta(minutes=3) # 유효한 이메일 판단 기준 시간 (현재로부터 X min까지)
check_interval = 5  # sec, 재조회 텀
timeout = 3 * 60 # 재조회 타임아웃 시간

# 학교로부터 온 가장 최근 메일 가져오기
def get_latest_email(mail):
    # INBOX 선택
    mail.select("inbox")
    # 특정 발신자의 메일 검색
    status, messages = mail.search(None, f'(FROM "{from_email}")')
    # 메일 ID 리스트 얻기
    mail_ids = messages[0].split()
    if not mail_ids:
        return None, None

    # 가장 최근 메일 ID 얻기
    latest_email_id = mail_ids[-1]
    # 가장 최근 메일 가져오기
    status, msg_data = mail.fetch(latest_email_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            return msg, latest_email_id
    return None, None


# 이메일에서 인증번호 꺼내기
def extract_verification_code(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/html" and "attachment" not in content_disposition:
                body = part.get_payload(decode=True).decode()
                return parse_verification_code_from_body(body)
    else:
        if msg.get_content_type() == "text/html":
            body = msg.get_payload(decode=True).decode()
            return parse_verification_code_from_body(body)
    return None


# 인증번호 숫자 꺼내기
def parse_verification_code_from_body(body):
    soup = BeautifulSoup(body, "html.parser")
    code = soup.find('b').text
    return code


# 이메일에서 인증번호 가져오기
def parse_verification_code_from_email():
    # IMAP 서버에 연결
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(gmail_id, gmail_pw)
    print("메일 서버 접속 성공")
    start_time = time.time()
    try:
        while True:
            msg, latest_email_id = get_latest_email(mail)
            if msg:
                # 메일 날짜 파싱
                mail_date = parsedate_to_datetime(msg["Date"])
                current_time = datetime.now(mail_date.tzinfo)

                if current_time - mail_date <= time_threshold:
                    # 메일 제목 디코딩
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    # 발신자 정보 디코딩
                    from_ = msg.get("From")
                    from_name, from_email = parseaddr(from_)
                    print("Subject:", subject)
                    print("From:", from_email)
                    # 메일 본문에서 인증번호 추출
                    verification_code = extract_verification_code(msg)
                    if verification_code:
                        print(f"인증번호: {verification_code}")
                        return verification_code
                    break
            print(f"인증 메일을 찾을 수 없어 {check_interval}초 후 재조회합니다.")
            time.sleep(check_interval)

            # 경과 시간 확인
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                print("최대 대기 시간을 초과했습니다. 인증 메일을 찾지 못했습니다.")
                break
    finally:
        mail.logout()
