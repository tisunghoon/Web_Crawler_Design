import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from web_crawler.config import DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)

MAX_CRAWL_DELAY = 300.0
REQUEST_TIMEOUT = 30
_DENIED_STATUSES = (401, 403)


@dataclass(frozen=True)
class _Rule:
    length: int  # 원래 패턴 길이. "가장 긴 패턴 우선" 비교에 쓴다
    regex: re.Pattern[str]


@dataclass
class RobotsRules:
    """`User-agent: *` 그룹의 규칙. RFC 9309 방식: `*`, `$` 지원, 가장 긴 패턴이 우선, 길이가 같으면 Allow 우선."""

    allow: list[_Rule] = field(default_factory=list)
    disallow: list[_Rule] = field(default_factory=list)
    crawl_delay: float | None = None

    @classmethod
    def parse(cls, text: str) -> "RobotsRules":
        rules = cls()
        applies = False  # 현재 그룹이 `*`를 포함하는지
        in_agent_lines = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            field_name, sep, value = line.partition(":")
            if not sep:
                continue
            field_name, value = field_name.strip().lower(), value.strip()
            if field_name == "user-agent":
                if not in_agent_lines:  # 새 그룹 시작
                    applies = False
                applies = applies or value == "*"
                in_agent_lines = True
                continue
            in_agent_lines = False
            if not applies:
                continue
            if field_name == "disallow" and value:
                rules.disallow.append(_compile(value))
            elif field_name == "allow" and value:
                rules.allow.append(_compile(value))
            elif field_name == "crawl-delay":
                try:
                    rules.crawl_delay = float(value)
                except ValueError:
                    logger.warning("잘못된 Crawl-delay 값을 무시합니다: %r", value)
        return rules

    @classmethod
    def disallow_all(cls) -> "RobotsRules":
        return cls(disallow=[_compile("/")])

    def is_allowed(self, path_and_query: str) -> bool:
        blocked = _longest_match(self.disallow, path_and_query)
        return blocked < 0 or _longest_match(self.allow, path_and_query) >= blocked


def _compile(pattern: str) -> _Rule:
    anchored = pattern.endswith("$")
    body = re.escape(pattern.removesuffix("$")).replace(r"\*", ".*")
    return _Rule(len(pattern), re.compile(body + (r"\Z" if anchored else "")))


def _longest_match(rules: list[_Rule], target: str) -> int:
    """일치하는 규칙 중 가장 긴 패턴의 길이. 일치하는 게 없으면 -1."""
    return max((r.length for r in rules if r.regex.match(target)), default=-1)


class RobotsTxtCache:
    """도메인(호스트:포트)별 robots.txt 규칙을 한 번만 가져와 캐시한다."""

    def __init__(self, user_agent: str = DEFAULT_USER_AGENT) -> None:
        self._user_agent = user_agent
        self._rules: dict[str, RobotsRules] = {}

    def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.netloc not in self._rules:
            self.fetch_and_cache(parsed.netloc, parsed.scheme)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        return self._rules[parsed.netloc].is_allowed(target)

    def get_crawl_delay(self, domain: str) -> float | None:
        rules = self._rules.get(domain)
        if rules is None or rules.crawl_delay is None:
            return None
        return min(rules.crawl_delay, MAX_CRAWL_DELAY)

    def fetch_and_cache(self, domain: str, scheme: str) -> None:
        """robots.txt를 요청해 캐시한다.

        200은 파싱한다. 401·403과 5xx, 요청 실패는 크롤링을 허락받지 못한 것이므로 전체 금지,
        그 외 응답(404, 410 등)은 규칙이 없는 것으로 보고 전체 허용이다.
        """
        robots_url = f"{scheme}://{domain}/robots.txt"
        try:
            response = requests.get(
                robots_url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": self._user_agent}
            )
        except requests.RequestException as e:
            logger.warning("robots.txt 요청 실패로 전체 금지 처리 url=%s: %s", robots_url, e)
            self._rules[domain] = RobotsRules.disallow_all()
            return

        status = response.status_code
        if status == 200:
            self._rules[domain] = RobotsRules.parse(response.text)
        elif status in _DENIED_STATUSES or status >= 500:
            logger.warning("robots.txt 접근 불가(status=%s)로 전체 금지 처리 url=%s", status, robots_url)
            self._rules[domain] = RobotsRules.disallow_all()
        else:
            logger.warning("robots.txt 없음(status=%s)으로 전체 허용 처리 url=%s", status, robots_url)
            self._rules[domain] = RobotsRules()
