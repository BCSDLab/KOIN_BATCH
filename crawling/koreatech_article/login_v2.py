import requests
import config
import re

LOGIN_COOKIE_NAME = '__KSMSID__'


def login():
    # 설정 불러오기

    headers = {
        "X-Forwarded-For": config.PORTAL_CONFIG["ip"],
        "X-Real-IP": config.PORTAL_CONFIG["ip"]
    }

    payload = {
        'login_id': config.PORTAL_CONFIG['id'],
        'login_pwd': config.PORTAL_CONFIG['pw'],
    }

    # 세션 생성
    session = requests.session()

    # 아우누리 로그인
    session.post(
        url="https://portal.koreatech.ac.kr/ktp/login/checkLoginId.do",
        headers=headers,
        data=payload,
        allow_redirects=True
    )

    session.cookies.set('kut_login_type', 'id')

    session.post(
        url="https://portal.koreatech.ac.kr/ktp/login/checkSecondLoginCert.do",
        headers=headers,
        data={
            'login_id': config.PORTAL_CONFIG['id']
        }
    )

    session.post(
        url="https://portal.koreatech.ac.kr/exsignon/sso/sso_assert.jsp",
        headers=headers
    )

    response = session.get(
        url="https://kut90.koreatech.ac.kr/ssoLogin_ext.jsp?&PGM_ID=CO::CO0998W&locale=ko",
        headers=headers
    )

    # 학생종합경력개발 로그인
    response = session.get(
        url="https://job.koreatech.ac.kr/",
        headers=headers
    )

    response = session.get(
        url="https://job.koreatech.ac.kr/Main/default.aspx",
        headers=headers
    )

    response = session.get(
        url="https://tsso.koreatech.ac.kr/svc/tk/Auth.do?id=STEMS-JOB&ac=N&ifa=N&RelayState=%2fMain%2fdefault.aspx&",
        headers=headers
    )

    # html에 있는 js 코드에서 쿠키 파싱
    html = response.text
    cookie_pattern = re.compile(r'document\.cookie\s*=\s*"([^=]+)=([^;]+);')
    parsed_cookies = {match.group(1): match.group(2) for match in cookie_pattern.finditer(html)}

    session.cookies.update(parsed_cookies)

    response = session.get(
        url="https://job.koreatech.ac.kr/Career/",
        headers=headers
    )

    return {cookie.name: cookie.value for cookie in session.cookies}


if __name__ == '__main__':
    print(login())
