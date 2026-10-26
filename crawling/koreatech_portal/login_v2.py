import requests
import config

LOGIN_COOKIE_NAME = 'JSESSIONID'

# SSO 인증 완료 시 포털이 발급하는 쿠키
AUTHENTICATED_COOKIE_NAME = 'userEmpno'


def portal_login():
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

    session.get(
        url="https://kut90.koreatech.ac.kr/ssoLogin_ext.jsp?&PGM_ID=CO::CO0998W&locale=ko",
        headers=headers,
        timeout=30
    )

    if not session.cookies.get(AUTHENTICATED_COOKIE_NAME):
        raise ConnectionError("포털 로그인 실패: SSO 인증 쿠키를 받지 못했습니다")

    return session.cookies


if __name__ == '__main__':
    cookies = portal_login()
    print("로그인 성공" if cookies.get(AUTHENTICATED_COOKIE_NAME) else "로그인 실패")
