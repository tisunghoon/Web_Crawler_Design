import logging
from collections import Counter
from urllib.parse import urlparse

from web_crawler.visited_store import VisitedURLStore

logger = logging.getLogger(__name__)

MAX_URL_LENGTH = 2048
MAX_SEGMENT_REPEAT = 3


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
