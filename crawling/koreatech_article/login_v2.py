import requests
import config
import re

LOGIN_COOKIE_NAME = '__KSMSID__'

# SSO 인증 완료 시 포털이 발급하는 쿠키
AUTHENTICATED_COOKIE_NAME = 'userEmpno'

# 게시판 크롤링에 필요한 쿠키
REQUIRED_COOKIES = ('JSESSIONID', 'ASP.NET_SessionId', 'mauth', 'hn_ck_login')


def login():
    # 설정 불러오기

    headers = {
        "X-Forwarded-For": config.PORTAL_CONFIG["ip"],
        "X-Real-IP": config.PORTAL_CONFIG["ip"]
    }

    payload = {
        'login_id': config.PORTAL_CONFIG['id'],
        'login_pwd': config.PORTAL_CONFIG['pw'],
        'login_type': '',
        'login_empno': '',
        'login_certDn': '',
        'login_certChannel': '',
    }

    # 세션 생성
    session = requests.session()

    # WAF가 POST를 400(evfw 챌린지)으로 차단하므로 전 구간 GET으로 로그인한다.
    try:
        login_result = session.get(
            url="https://portal.koreatech.ac.kr/ktp/login/checkLoginId.do",
            headers=headers,
            params=payload,
            allow_redirects=True,
            timeout=30
        )
        login_result.raise_for_status()
        result = login_result.json()
    except (requests.RequestException, ValueError):
        # 요청 URL에 인증 정보가 있으므로 원본 예외와 응답 본문을 출력하지 않는다.
        raise ConnectionError("포털 로그인 요청 실패") from None
    if not isinstance(result, dict) or result.get('result') != 'true':
        raise ConnectionError("포털 로그인 실패")

    session.cookies.set('kut_login_type', 'id')

    session.get(
        url="https://portal.koreatech.ac.kr/ktp/login/checkSecondLoginCert.do",
        headers=headers,
        params={
            'login_id': config.PORTAL_CONFIG['id']
        },
        timeout=30
    )

    session.get(
        url="https://portal.koreatech.ac.kr/exsignon/sso/sso_assert.jsp",
        headers=headers,
        timeout=30
    )

    if not session.cookies.get(AUTHENTICATED_COOKIE_NAME):
        raise ConnectionError("포털 로그인 실패: SSO 인증 쿠키를 받지 못했습니다")

    response = session.get(
        url="https://kut90.koreatech.ac.kr/ssoLogin_ext.jsp?&PGM_ID=CO::CO0998W&locale=ko",
        headers=headers,
        timeout=30
    )

    # 학생종합경력개발 로그인
    response = session.get(
        url="https://job.koreatech.ac.kr/",
        headers=headers,
        timeout=30
    )

    response = session.get(
        url="https://job.koreatech.ac.kr/Main/default.aspx",
        headers=headers,
        timeout=30
    )

    response = session.get(
        url="https://tsso.koreatech.ac.kr/svc/tk/Auth.do?id=STEMS-JOB&ac=N&ifa=N&RelayState=%2fMain%2fdefault.aspx&",
        headers=headers,
        timeout=30
    )

    # html에 있는 js 코드에서 쿠키 파싱
    html = response.text
    cookie_pattern = re.compile(r'document\.cookie\s*=\s*"([^=]+)=([^;]+);')
    parsed_cookies = {match.group(1): match.group(2) for match in cookie_pattern.finditer(html)}

    session.cookies.update(parsed_cookies)

    response = session.get(
        url="https://job.koreatech.ac.kr/Career/",
        headers=headers,
        timeout=30
    )

    # JSESSIONID는 portal/ kut90 양쪽에 발급되므로 도메인을 구분해 담는다.
    # dict로 평탄화하면 kut90 세션이 portal 세션을 덮어써 게시판 조회가 깨진다.
    login_cookie = {cookie.name: cookie.value for cookie in session.cookies}
    login_cookie['JSESSIONID'] = session.cookies.get('JSESSIONID', domain='portal.koreatech.ac.kr')

    missing = [name for name in REQUIRED_COOKIES if not login_cookie.get(name)]
    if missing:
        raise ConnectionError(f"게시판 로그인 실패: 쿠키 누락 {missing}")

    return login_cookie


if __name__ == '__main__':
    print("로그인 성공" if login() else "로그인 실패")
