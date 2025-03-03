import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import config
import requests

# 알림창 닫기
def check_for_alert(driver, timeout=5):
    try:
        WebDriverWait(driver, timeout).until(EC.alert_is_present())
        alert = driver.switch_to.alert
        alert.accept()
        print("알림창 제거")
    except:
        print("알림창 없음")


# Chrome DevTools Protocol(CDP)를 이용하여 헤더를 추가
def insert_header(driver):
    driver.execute_cdp_cmd(
        "Network.setExtraHTTPHeaders",
        {'headers': {
            "X-Forwarded-For": config.PORTAL_CONFIG["ip"],
            "X-Real-IP": config.PORTAL_CONFIG["ip"]
        }}
    )


def login():
    # 설정 불러오기
    koreatech_id = config.PORTAL_CONFIG['id']
    koreatech_pw = config.PORTAL_CONFIG['pw']

    portal_url = "https://portal.koreatech.ac.kr/"
    job_url = "https://job.koreatech.ac.kr/"

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

    # Chrome DevTools Protocol(CDP) 활성화
    driver.execute_cdp_cmd("Network.enable", {})

    # 헤더 추가
    insert_header(driver)

    try:
        # 웹사이트로 이동
        driver.get(url=f'{portal_url}login.jsp')

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

        # 비밀번호 변경 페이지
        if url.startswith(f"{portal_url}proc/Login.do?user_id="):
            print("비밀번호 변경 페이지 진입")
            nextTimeChangeButton = driver.find_element(
                By.XPATH,
                '//*[@id="pwdUpdateFrm"]/div/div/div[3]/div/ul/li[2]/a'
            )
            nextTimeChangeButton.click()
            check_for_alert(driver)
            time.sleep(5)
            url = driver.current_url

        # 아우누리 페이지
        if url == f"{portal_url}p/STHOME/":
            print('로그인 성공')
        else:
            print(f"로그인 실패 - 예상치 못한 url 접근: {url}")
            return None

        cookies = {cookie['name']: cookie for cookie in driver.get_cookies()}

        print("job 로그인 시도")
        driver.get(url=job_url)

        # URL에 따라 분기
        time.sleep(5)
        url = driver.current_url

        time.sleep(3)
        check_for_alert(driver)

        # job 페이지
        if url == job_url:
            print('job 로그인 성공')
            for cookie in driver.get_cookies():
                cookies[cookie['name']] = cookie
        else:
            print('job 로그인 실패 - 예상치 못한 url 접근: ' + url)

        return cookies
    except Exception as e:
        print('job 로그인 실패 - 로직 수행 간 오류 발생')
        print(e)
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

# 코인 사이트 JWT 토큰 발급 함수
def get_jwt_token():
    login_url = config.BATCH_CONFIG['token_url'] 
    credentials = {
        'email': config.BATCH_CONFIG['email'],
        'password': config.BATCH_CONFIG['password']
    }

    return requests.post(login_url, json=credentials).json().get('token')

if __name__ == '__main__':
    print(login())
