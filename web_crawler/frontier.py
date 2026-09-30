import heapq
import itertools
import time
from collections import deque
from collections.abc import Callable
from urllib.parse import urlparse


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:  # 파싱 불가 URL은 빈 호스트 버킷으로 보내고 필터가 거부한다
        return ""


class URLFrontier:
    """우선순위 Front Queue와 호스트별 예의(Politeness) Back Queue."""

    def __init__(
        self,
        politeness_delay: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._default_delay = politeness_delay
        self._clock = clock
        self._sleep = sleep
        self._front: list[tuple[float, int, str, int]] = []
        self._seq = itertools.count()
        self._seen: set[str] = set()
        self._back: dict[str, deque[tuple[str, int]]] = {}
        self._last_request: dict[str, float] = {}
        self._host_delay: dict[str, float] = {}

    def push(self, url: str, priority: float, depth: int) -> bool:
        """Front Queue에 삽입한다. 이미 삽입된 URL(완전 일치)이면 False."""
        if url in self._seen:
            return False
        self._seen.add(url)
        # 최대 힙: 우선순위를 음수로, 동점은 삽입 순번으로 FIFO
        heapq.heappush(self._front, (-priority, next(self._seq), url, depth))
        return True

    def pop(self) -> tuple[str, int] | None:
        """최우선 URL을 호스트 버킷으로 라우팅하고, Politeness_Delay를 지켜 반환한다."""
        if not self._front:
            return None
        _, _, url, depth = heapq.heappop(self._front)
        host = _host(url)
        bucket = self._back.setdefault(host, deque())
        bucket.append((url, depth))
        self._wait_for_turn(host)
        self._last_request[host] = self._clock()
        return bucket.popleft()

    def is_empty(self) -> bool:
        return not self._front and not any(self._back.values())

    def set_host_delay(self, host: str, seconds: float) -> None:
        """호스트별 Politeness_Delay를 지정한다. 기본값보다 우선한다."""
        self._host_delay[host.lower()] = seconds

    def _wait_for_turn(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is None:
            return
        delay = self._host_delay.get(host, self._default_delay)
        remaining = delay - (self._clock() - last)
        if remaining > 0:
            self._sleep(remaining)
