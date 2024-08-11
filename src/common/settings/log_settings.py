"""
로그 설정 파일

참고: https://docs.scrapy.org/en/latest/topics/settings.html#log-enabled
"""

LOG_ENABLED = True
"""
로깅 활성화 여부입니다.

기본값: ``True``
"""

LOG_ENCODING = 'utf-8'
"""
로깅에 사용할 인코딩입니다.

기본값: ``'utf-8'``
"""

LOG_FILE = 'logs/scrapy.log'
"""
로깅 출력에 사용할 파일 이름입니다. ``None`` 이면 표준 오류가 사용됩니다.

기본값: ``None``
"""

LOG_FILE_APPEND = True
"""
``False`` 를 선택하면 ``LOG_FILE`` 로 지정된 로그 파일을 덮어씁니다(이전 실행의 출력이 있는 경우 삭제).

기본값: ``True``
"""

LOG_FORMAT = '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
"""
로그 메시지 서식을 지정하는 문자열입니다.

사용 가능한 자리 표시자의 전체 목록은 `Python 로깅 설명서 <https://docs.python.org/3/library/logging.html#logrecord-attributes>`_
를 참조하세요.

기본값: ``'%(asctime)s [%(name)s] %(levelname)s: %(message)s'``
"""

LOG_DATEFORMAT = '%Y-%m-%d %H:%M:%S'
"""
날짜/시간 서식을 지정하기 위한 문자열, ``LOG_FORMAT`` 에서 ``%(asctime)s`` 의 자리 표시자를 확장합니다.

사용 가능한 전체 지시어 목록은 `파이썬 날짜/시간 설명서 <https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior>`_
를 참조하세요.

기본값: ``'%Y-%m-%d %H:%M:%S'``

"""

LOG_FORMATTER = 'scrapy.logformatter.LogFormatter'
"""
다양한 작업에 대한 `로그 메시지 서식을 지정 <https://docs.scrapy.org/en/latest/topics/logging.html#custom-log-formats>`_
하는 데 사용할 클래스입니다.

기본값: `'scrapy.logformatter.LogFormatter' <https://docs.scrapy.org/en/latest/topics/logging.html#scrapy.logformatter.LogFormatter>`_
"""

LOG_LEVEL = 'INFO'
"""
기록할 최소 레벨입니다. 사용 가능한 레벨은 다음과 같습니다: ``CRITICAL``, ``ERROR``, ``WARNING``, ``INFO``, ``DEBUG`` 입니다.

자세한 내용은 `Logging <https://docs.scrapy.org/en/latest/topics/logging.html#topics-logging>`_ 을 참조하세요.

기본값: ``'DEBUG'``
"""

LOG_STDOUT = False
"""
``True`` 로 설정하면 프로세스의 모든 표준 출력(및 오류)이 로그로 리디렉션됩니다.

예를 들어 ``print('hello')`` 를 실행하면 스크랩 로그에 표시됩니다.

기본값: ``False``
"""

LOG_SHORT_NAMES = False
"""
``True`` 로 설정하면 로그에 루트 경로만 포함됩니다. ``False`` 로 설정하면 로그 출력을 담당하는 컴포넌트를 표시합니다.

기본값: ``False``
"""

LOGSTATS_INTERVAL = 60.0
"""
`LogStats <https://docs.scrapy.org/en/latest/topics/extensions.html#scrapy.extensions.logstats.LogStats>`_
에 의한 통계의 각 로깅 출력 사이의 간격(초)입니다.

기본값: ``60.0``
"""

LOG_DIR = 'logs'
"""
크롤러(Spider) 로깅 출력에 사용할 폴더 입니다. *커스텀 설정 값입니다.*

기본값: ``'logs'``
"""