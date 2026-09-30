import logging
import time
from collections.abc import Callable
from urllib.parse import urljoin

import requests
from bs4 import UnicodeDammit

from web_crawler.config import DEFAULT_USER_AGENT
from web_crawler.models import DownloadResult
from web_crawler.robots_cache import RobotsTxtCache
from web_crawler.visited_store import VisitedURLStore

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 2
RETRY_INTERVAL = 5
MAX_REDIRECTS = 5


class Downloader:
    def __init__(
        self,
        robots: RobotsTxtCache,
        visited: VisitedURLStore,
        sleep: Callable[[float], None] = time.sleep,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self._robots = robots
        self._headers = {"User-Agent": user_agent}
        self._visited = visited
        self._sleep = sleep
        self._redirect_hops: dict[str, int] = {}

    def download(self, url: str, depth: int = 0) -> DownloadResult:
        if not self._robots.is_allowed(url):
            logger.warning("robots.txt Disallow로 건너뜀 url=%s", url)
            return DownloadResult(url, "skipped", error_reason="robots.txt Disallow")

        response, failure = self._get_with_retry(url)
        if response is None:
            logger.error("다운로드 최종 실패 url=%s: %s", url, failure)
            self._visited.add(url)
            return DownloadResult(url, "error", error_reason=failure)
        return self._handle_response(url, response)

    def _get_with_retry(self, url: str) -> tuple[requests.Response | None, str]:
        """5xx와 네트워크 오류는 5초 간격으로 최대 2회 재시도한다."""
        failure = ""
        for attempt in range(MAX_RETRIES + 1):
            if attempt:
                self._sleep(RETRY_INTERVAL)
            try:
                response = requests.get(
                    url, timeout=REQUEST_TIMEOUT, allow_redirects=False, headers=self._headers
                )
            except ValueError as e:  # InvalidURL 포함. 예: Location이 "http://[bad"는 재시도해도 같다
                return None, f"잘못된 URL 또는 Location: {e}"
            except requests.RequestException as e:
                failure = f"요청 실패: {e}"
                continue
            if response.status_code < 500:
                return response, ""
            failure = f"HTTP {response.status_code}"
        return None, failure

    def _handle_response(self, url: str, response: requests.Response) -> DownloadResult:
        status = response.status_code
        if status == 200:
            self._visited.add(url)
            content_type = response.headers.get("Content-Type", "")
            if not content_type.lower().startswith("text/html"):
                logger.debug("HTML이 아니라 건너뜀 url=%s content-type=%r", url, content_type)
                return DownloadResult(url, "skipped", error_reason="Content-Type이 text/html이 아님")
            return DownloadResult(url, "ok", html=self._decode(response))
        if status in (301, 302):
            return self._handle_redirect(url, response)

        self._visited.add(url)
        logger.warning("HTTP %s로 건너뜀 url=%s", status, url)
        return DownloadResult(url, "skipped", error_reason=f"HTTP {status}")

    @staticmethod
    def _decode(response: requests.Response) -> str:
        """헤더에 charset이 없으면 requests가 ISO-8859-1로 가정하므로 본문 바이트에서 직접 판별한다."""
        if "charset" in response.headers.get("Content-Type", "").lower():
            return response.text
        return UnicodeDammit(response.content, is_html=True).unicode_markup or ""

    def _handle_redirect(self, url: str, response: requests.Response) -> DownloadResult:
        self._visited.add(url)
        location = response.headers.get("Location")
        hops = self._redirect_hops.get(url, 0) + 1
        if not location:
            return self._redirect_error(url, "Location 헤더 없음")
        if hops > MAX_REDIRECTS:
            return self._redirect_error(url, f"리다이렉트 {MAX_REDIRECTS}회 초과")
        target = urljoin(url, location)
        self._redirect_hops[target] = hops
        return DownloadResult(url, "redirect", redirect_url=target)

    @staticmethod
    def _redirect_error(url: str, reason: str) -> DownloadResult:
        logger.error("리다이렉트 중단 url=%s: %s", url, reason)
        return DownloadResult(url, "error", error_reason=reason)
