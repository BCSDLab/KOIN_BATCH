from pathlib import Path
from scrapy import signals
from scrapy.utils.log import configure_logging, DEFAULT_LOGGING


class SpiderLoggingExtension:
    def __init__(self, log_dir):
        self.log_dir = Path(log_dir)

    @classmethod
    def from_crawler(cls, crawler):
        log_dir = crawler.settings.get('LOG_DIR')

        ext = cls(log_dir)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        return ext

    def spider_opened(self, spider):
        # LOG_DIR가 없으면 로그 생성하지 않음
        if self.log_dir is None:
            return

        log_file = self.get_log_file(spider)

        # Scrapy의 기본 로깅 설정을 복사
        settings = DEFAULT_LOGGING.copy()

        # 로그 파일 경로를 설정
        settings["LOG_FILE"] = log_file

        # 로깅을 구성
        configure_logging(settings)

    def get_log_file(self, spider):
        module_path = Path(spider.__module__.replace('.', '/'))

        # 'src'이후 부터 시작하는 경로 생성
        parts = module_path.parts
        if 'src' in module_path.parts:
            parts = module_path.parts[module_path.parts.index('src') + 1:]

        spider_path = module_path
        if 'crawling' in parts:
            spider_path = Path(*parts[parts.index('crawling'):])

        # spider 이름을 경로에 추가
        spider_path = spider_path.parent / spider.name

        log_file = self.log_dir / f"{spider_path}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        return log_file

