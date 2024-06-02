import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gmail_verification import parse_verification_code_from_email
import config

# 알림창 닫기
def check_for_alert(driver, timeout=5):
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert.accept()
        print("알림창 제거")
    except:
        print("알림창 없음")

def portal_login():
    # 설정 불러오기
    koreatech_id = config.PORTAL_CONFIG['id']
    koreatech_pw = config.PORTAL_CONFIG['pw']

    # Chrome 드라이버 설정
    options = Options()

    # 리눅스 환경에서만 활성화 - 셀레니움 GUI off
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # 기타 기본 설정
    options.add_argument("disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        # 웹사이트로 이동
        driver.get(url='https://portal.koreatech.ac.kr/login.jsp')

        # 아이디 비밀번호 입력란 탐색
        wait = WebDriverWait(driver, 5)
        id = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="user_id"]')))
        pw = driver.find_element(By.XPATH, '//*[@id="user_pwd"]')
        loginButton = driver.find_element(By.XPATH, '//*[@id="ssoLoginFrm"]/ul[2]/li[1]/a')
        print("로그인 화면 진입")

        # 로그인
        id.send_keys(koreatech_id)
        pw.send_keys(koreatech_pw)
        loginButton.click()
        print("로그인 시도")

        # URL에 따라 분기
        time.sleep(5)
        url = driver.current_url

        # 교외 인증 페이지
        if url == "https://portal.koreatech.ac.kr/kut/page/secondCertIp.jsp":
            print('2차 인증 필요')
            radioButton = driver.find_element(By.XPATH, '//*[@id="typeEmail"]')
            textbox = driver.find_element(By.XPATH, '//*[@id="resEmailCertKey"]')
            sendButton = driver.find_element(By.XPATH, '//*[@id="CertTypeEmailRow"]/td/ul/li[1]/input[2]')
            authButton = driver.find_element(By.XPATH, '//*[@id="findPwContent"]/table/tbody/tr[4]/td/ul/li[2]/input')
            radioButton.click()
            sendButton.click()
            print("이메일 전송")
            # 알림창 나오면 닫기
            check_for_alert(driver)
            # 인증번호 가져옴
            verificationCode = parse_verification_code_from_email()
            print("인증번호 추출 완료")
            textbox.send_keys(verificationCode)
            authButton.click()
            time.sleep(5)
            url = driver.current_url

        # 비밀번호 변경 페이지
        if url.startswith("https://portal.koreatech.ac.kr/proc/Login.do?user_id="):
            print("비밀번호 변경 페이지 진입")
            nextTimeChangeButton = driver.find_element(By.XPATH, '//*[@id="pwdUpdateFrm"]/div/div/div[3]/div/ul/li[2]/a')
            nextTimeChangeButton.click()
            check_for_alert(driver)
            time.sleep(5)
            url = driver.current_url

        # 아우누리 페이지
        if url == "https://portal.koreatech.ac.kr/p/STHOME/":
            print('로그인 성공')
            cookies = driver.get_cookies()
            cookie_dict = {}
            for cookie in cookies:
                cookie_dict[cookie['name']] = cookie['value']
            return cookie_dict
        else:
            print('로그인 실패 - 예상치 못한 url 접근: ' + url)
            return None
    except:
        print('로그인 실패 - 로직 수행 간 오류 발생')
        return None
    finally:
        driver.quit()


"""
비밀번호 변경 페이지 elements XPATH

## input text (READ ONLY, 자동 입력됨)
사용자 ID: //*[@id="loginId"]
학생/교직원번호: //*[@id="empno"]

## input text
이전 비밀번호: //*[@id="prePwd"]
신규 비밀번호: //*[@id="newPwd"]
신규 비밀번호 확인: //*[@id="confirmNewPwd"]

## button
비밀번호 변경: //*[@id="pwdUpdateFrm"]/div/div/div[3]/div/ul/li[1]/a
다음에 변경: //*[@id="pwdUpdateFrm"]/div/div/div[3]/div/ul/li[2]/a
"""