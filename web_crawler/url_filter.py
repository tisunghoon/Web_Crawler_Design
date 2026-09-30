import logging
from collections import Counter
from urllib.parse import urlparse

from urllib3.exceptions import LocationParseError
from urllib3.util import parse_url

from web_crawler.visited_store import VisitedURLStore

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048
MAX_SEGMENT_REPEAT = 3


def _normalized(host: str | None) -> str | None:
    """대소문자, IPv6 대괄호, IDN(퓨니코드) 표기 차이를 없앤 호스트."""
    if not host:
        return None
    host = host.strip("[]").lower()
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def hosts_agree(url: str) -> bool:
    """urlparse와 HTTP 클라이언트(urllib3)가 같은 호스트로 해석하는 URL인지.

    예를 들어 "http://evil.com\\@a.com/"은 urlparse가 a.com, requests가 evil.com으로 읽는다.
    범위 판정과 robots.txt, DNS가 실제 접속 호스트와 다른 호스트를 보지 않도록 입구에서 거른다.
    """
    try:
        parsed_host = _normalized(urlparse(url).hostname)
        client_host = _normalized(parse_url(url).host)
    except (ValueError, LocationParseError):
        return False
    return parsed_host is not None and parsed_host == client_host


class URLFilter:
    """크롤링 허용 여부를 판단한다. 첫 번째로 감지한 위반만 사유로 반환한다."""

    def __init__(self, visited: VisitedURLStore, max_depth: int) -> None:
        self._visited = visited
        self._max_depth = max_depth

    def is_allowed(self, url: str, depth: int) -> tuple[bool, str | None]:
        reason = self._first_violation(url, depth)
        if reason:
            logger.warning("URL 거부 url=%s 사유=%s", url, reason)
            return False, reason
        return True, None

    def _first_violation(self, url: str, depth: int) -> str | None:
        try:
            parsed = urlparse(url)
        except ValueError:  # 예: "http://[bad" (잘못된 IPv6 리터럴)
            return "URL 형식 오류"
        if parsed.scheme.lower() not in ("http", "https"):
            return "스킴 오류"
        if not hosts_agree(url):
            return "URL 형식 오류"
        if len(url) > MAX_URL_LENGTH:
            return "길이 초과"
        if depth > self._max_depth:
            return "깊이 초과"
        if self._has_repeated_segment(parsed.path):
            return "경로 반복"
        if self._visited.contains(url):
            return "이미 방문"
        return None

    @staticmethod
    def _has_repeated_segment(path: str) -> bool:
        segments = Counter(s.lower() for s in path.split("/") if s)
        return any(n >= MAX_SEGMENT_REPEAT for n in segments.values())
