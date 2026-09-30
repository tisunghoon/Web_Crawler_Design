import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

logger = logging.getLogger(__name__)

MAX_CRAWL_DELAY = 300.0
REQUEST_TIMEOUT = 30
_USER_AGENT = "*"


class RobotsTxtCache:
    """도메인(호스트:포트)별 robots.txt 규칙을 한 번만 가져와 캐시한다."""

    def __init__(self) -> None:
        self._rules: dict[str, RobotFileParser] = {}

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc not in self._rules:
            self.fetch_and_cache(parsed.netloc, parsed.scheme)
        return self._rules[parsed.netloc].can_fetch(_USER_AGENT, url)

    def get_crawl_delay(self, domain: str) -> float | None:
        rules = self._rules.get(domain)
        delay = rules.crawl_delay(_USER_AGENT) if rules else None
        return None if delay is None else min(float(delay), MAX_CRAWL_DELAY)

    def fetch_and_cache(self, domain: str, scheme: str) -> None:
        """robots.txt를 요청해 캐시한다. 실패하거나 없으면 전체 허용 규칙을 저장한다."""
        robots_url = f"{scheme}://{domain}/robots.txt"
        rules = RobotFileParser()
        lines: list[str] = []
        try:
            response = requests.get(robots_url, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as e:
            logger.warning("robots.txt 요청 실패 url=%s: %s", robots_url, e)
        else:
            if response.status_code == 200:
                lines = response.text.splitlines()
            else:
                logger.warning("robots.txt 없음 url=%s status=%s", robots_url, response.status_code)
        rules.parse(lines)
        self._rules[domain] = rules
