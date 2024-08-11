import logging
from pathlib import Path

from scrapy import signals
from scrapy.crawler import Crawler


class SpiderLoggingExtension:
    def __init__(self, log_dir: str, log_formatter: logging.Formatter, log_level: str) -> None:
        self.log_dir = Path(log_dir)
        self.log_formatter = log_formatter
        self.log_level = log_level

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> 'SpiderLoggingExtension':
        log_dir = crawler.settings.get('LOG_DIR')
        log_format = crawler.settings.get('LOG_FORMAT')
        log_dateformat = crawler.settings.get('LOG_DATEFORMAT')
        log_level = crawler.settings.get('LOG_LEVEL')

        log_formatter = logging.Formatter(fmt=log_format, datefmt=log_dateformat)

        ext = cls(log_dir, log_formatter, log_level)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        return ext

    def spider_opened(self, spider):
        # LOG_DIR가 없으면 로그 생성하지 않음
        if self.log_dir is None:
            return

        log_file = self.get_log_file(spider)

        # 파일 핸들러 추가
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(self.log_formatter)

        # Spider 전용 로거 생성
        logger = logging.getLogger(spider.name)
        logger.propagate = False
        logger.addHandler(file_handler)
        logger.setLevel(self.log_level)

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

        log_file = self.log_dir / f'{spider_path}.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        return log_file
