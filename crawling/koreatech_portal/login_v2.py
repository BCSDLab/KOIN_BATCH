import requests
import config

LOGIN_COOKIE_NAME = '__KSMSID__'


def portal_login():
    # 설정 불러오기

    headers = {
        "X-Forwarded-For": config.PORTAL_CONFIG["ip"],
        "X-Real-IP": config.PORTAL_CONFIG["ip"]
    }

    payload = {
        'login_id': config.PORTAL_CONFIG['id'],
        'login_pwd': config.PORTAL_CONFIG['pw'],
    }

    session = requests.session()

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

    return {cookie.name: cookie.value for cookie in session.cookies}


if __name__ == '__main__':
    print(portal_login()['__KSMSID__'])
