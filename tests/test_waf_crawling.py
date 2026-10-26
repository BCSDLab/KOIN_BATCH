"""Offline regressions for portal WAF integration; no real config is imported."""
import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[1] / 'crawling'
CONFIG = ModuleType('config')
CONFIG.PORTAL_CONFIG = {'id': 'synthetic-user', 'pw': 'synthetic-password', 'ip': '192.0.2.1'}
CONFIG.MYSQL_CONFIG = CONFIG.BATCH_CONFIG = CONFIG.REDIS_CONFIG = {}
DINING_COOKIES = {'JSESSIONID': 'dining-session', '__KSMSID__': 'sso-session', 'KHANUSER': 'dining-user'}


def load_module(folder, name, **imports):
    spec = importlib.util.spec_from_file_location(f'waf_{folder}_{name}', ROOT / folder / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'config': CONFIG, **imports}):
        spec.loader.exec_module(module)
    return module


def cookie_jar(authenticated=True):
    jar = requests.cookies.RequestsCookieJar()
    for name, value, domain in [
        ('JSESSIONID', 'portal-session', 'portal.koreatech.ac.kr'),
        ('JSESSIONID', 'dining-session', 'kut90.koreatech.ac.kr'),
        ('__KSMSID__', 'sso-session', '.koreatech.ac.kr'),
        ('KHANUSER', 'dining-user', 'kut90.koreatech.ac.kr'),
        ('ASP.NET_SessionId', 'job-session', 'job.koreatech.ac.kr'),
        ('mauth', 'job-auth', 'job.koreatech.ac.kr'),
        ('hn_ck_login', 'job-login', 'job.koreatech.ac.kr'),
    ]:
        jar.set(name, value, domain=domain)
    if authenticated:
        jar.set('userEmpno', 'employee', domain='.koreatech.ac.kr')
    return jar


def response(text):
    result = requests.Response()
    result.status_code = 200
    result._content = text.encode()
    result.encoding = 'utf-8'
    return result


class WafCrawlingTests(unittest.TestCase):
    def setUp(self):
        # Fail closed on any HTTP call not explicitly replaced by a fixture.
        self.enterContext(patch.object(requests.sessions.Session, 'request', side_effect=AssertionError('Unexpected network call')))
        blocked = lambda: Mock(side_effect=AssertionError('Unexpected external service call'))
        self.portal = load_module('koreatech_portal', 'login_v2')
        self.article_login = load_module('koreatech_article', 'login_v2')
        self.dining = load_module('koreatech_portal', 'dining', login_v2=self.portal,
                                  pymysql=SimpleNamespace(connect=blocked()), redis=SimpleNamespace(StrictRedis=blocked()))
        self.article = load_module('koreatech_article', 'article', login_v2=self.article_login,
            pymysql=SimpleNamespace(connect=blocked()),
            delete_article=SimpleNamespace(delete_article=blocked()),
            table=SimpleNamespace(replace_table=blocked(), upload_txt=blocked()),
            login=SimpleNamespace(get_jwt_token=blocked()),
            slack_notice=SimpleNamespace(filter_nas=blocked(), notice_to_slack=blocked(),
                BUS_TIMETABLE_TITLE_PATTERN='', COOP_BUSINESS_HOURS_TITLE_PATTERN='', LECTURE_REGISTRATION_TITLE_PATTERN=''))
        self.output = io.StringIO()
        self.enterContext(redirect_stdout(self.output))
        self.enterContext(redirect_stderr(self.output))

    def run_login(self, module, body, authenticated=True):
        session = requests.Session()
        session.cookies = cookie_jar(authenticated)
        # Exercise parsing and cookie selection without prescribing an HTTP verb.
        with patch.object(session, 'request', return_value=response(body)), \
             patch.object(module.requests, 'session', return_value=session):
            return (module.portal_login if module is self.portal else module.login)()

    def test_both_logins_accept_json_whitespace(self):
        for module in (self.portal, self.article_login):
            with self.subTest(module=module.__name__):
                cookies = self.run_login(module, '{\n  "result" : "true"\n}')
                self.assertEqual(cookies.get('userEmpno'), 'employee')

    def test_both_logins_reject_failure_without_disclosing_response_or_credentials(self):
        for module in (self.portal, self.article_login):
            for body in (json.dumps({'result': 'false', 'detail': 'private-response synthetic-user synthetic-password'}),
                         '<html>private-response synthetic-user synthetic-password</html>'):
                with self.subTest(module=module.__name__, body=body):
                    with self.assertRaises(ConnectionError) as error:
                        self.run_login(module, body)
                    visible = str(error.exception) + self.output.getvalue()
                    for secret in ('private-response', 'synthetic-user', 'synthetic-password', body):
                        self.assertNotIn(secret, visible)

    def test_both_logins_require_user_empno(self):
        for module in (self.portal, self.article_login):
            with self.subTest(module=module.__name__):
                with self.assertRaises(ConnectionError):
                    self.run_login(module, '{"result":"true"}', authenticated=False)

    def test_both_logins_hide_credentials_in_transport_errors(self):
        for module in (self.portal, self.article_login):
            with self.subTest(module=module.__name__):
                session = Mock()
                session.get.side_effect = requests.Timeout('login_pwd=synthetic-password')
                with patch.object(module.requests, 'session', return_value=session):
                    with self.assertRaises(ConnectionError) as error:
                        (module.portal_login if module is self.portal else module.login)()
                self.assertNotIn('synthetic-password', str(error.exception))
                self.assertTrue(error.exception.__suppress_context__)

    def test_article_reports_missing_cookies_only_for_authenticated_boards(self):
        board = self.article.Board(17, '취업공지', 'job_notice', True, True)
        with patch.object(self.article, 'login_cookie', {}, create=True):
            with self.assertRaisesRegex(ConnectionError, '게시판 로그인 쿠키 누락'):
                self.article.get_cookies(board)
            board.need_login = False
            self.assertIsNone(self.article.get_cookies(board))

    def test_article_login_selects_portal_session_with_duplicate_cookie_names(self):
        cookies = self.run_login(self.article_login, '{"result":"true"}')
        self.assertEqual(cookies['JSESSIONID'], 'portal-session')

    def test_dining_sends_khanuser(self):
        with patch.object(self.dining.requests, 'request', return_value=response('<Root><Parameter id="ErrorCode">0</Parameter></Root>')) as send:
            self.dining.send_request(DINING_COOKIES, '2026-10-26', 'lunch', '한식', 'Campus1')
        self.assertEqual(send.call_args.kwargs['cookies'], DINING_COOKIES)

    def test_dining_missing_error_code_raises_connection_error(self):
        with patch.object(self.dining.requests, 'request', return_value=response('<html>WAF challenge</html>')):
            with self.assertRaises(ConnectionError):
                self.dining.send_request(DINING_COOKIES, '2026-10-26', 'lunch', '한식', 'Campus1')

    def test_dining_skips_incomplete_cache_and_validates_before_writing(self):
        for missing in DINING_COOKIES:
            with self.subTest(missing=missing):
                cache = Mock()
                cache.get.side_effect = lambda name: None if name == missing else b'cached'
                events = []
                cache.set.side_effect = lambda name, value: events.append(('write', name, value))
                def validate(cookies, *args):
                    events.append(('validate', cookies.copy()))
                with patch.object(self.dining, 'redis_client', cache), \
                     patch.object(self.dining, 'portal_login', return_value=cookie_jar()), \
                     patch.object(self.dining, 'send_request', side_effect=validate):
                    result = self.dining.get_cookie()
                self.assertEqual(result, DINING_COOKIES)
                self.assertEqual(events[0], ('validate', DINING_COOKIES))
                self.assertCountEqual(events[1:], [('write', k, v) for k, v in DINING_COOKIES.items()])

    def test_dining_never_caches_new_cookies_that_fail_validation(self):
        cache = Mock()
        cache.get.return_value = None
        with patch.object(self.dining, 'redis_client', cache), \
             patch.object(self.dining, 'portal_login', return_value=cookie_jar()) as login, \
             patch.object(self.dining, 'send_request', side_effect=ConnectionError('invalid session')):
            with self.assertRaises(ConnectionError):
                self.dining.get_cookie()
        login.assert_called_once()
        cache.set.assert_not_called()

    def test_article_skips_non_article_rows_and_processes_openw_relative_links(self):
        for ignored in ('<td>No anchor</td>', '<td><a onclick="urllink(\'242\',\'https://example.org\')">External</a></td>'):
            with self.subTest(ignored=ignored):
                html = '<table id="tbody_list1"><tbody><tr>' + ignored + '</tr><tr><td><a onclick="openw(\'/Community/Notice/NoticeView.aspx?num=42\')">Notice</a></td></tr></tbody></table>'
                board = self.article.Board(17, '취업공지', 'job_notice', True, True)
                found = SimpleNamespace(num=42)
                with patch.object(self.article, 'get_cookies', return_value={}), \
                     patch.object(self.article.requests, 'get', return_value=response(html)), \
                     patch.object(self.article, 'crawling_job_article', return_value=found) as fetch:
                    articles = self.article.crawling_job(board, 1)
                self.assertEqual(articles, [found])
                fetch.assert_called_once_with(board, 'https://job.koreatech.ac.kr', 'https://job.koreatech.ac.kr/Community/Notice/NoticeView.aspx?num=42')


if __name__ == '__main__':
    unittest.main()
