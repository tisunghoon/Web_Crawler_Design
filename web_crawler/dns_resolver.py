import logging
import socket
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

DEFAULT_TTL = 600.0


class DNSResolver:
    """호스트별 IP를 TTL 동안 캐시한다. 조회 실패는 None으로 알린다."""

    def __init__(
        self,
        ttl: float = DEFAULT_TTL,
        lookup: Callable[[str], str] = socket.gethostbyname,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._ttl = ttl
        self._lookup = lookup
        self._clock = clock
        self._cache: dict[str, tuple[str, float]] = {}

    def resolve(self, host: str) -> str | None:
        cached = self._cache.get(host)
        if cached:
            ip, expire_at = cached
            if self._clock() < expire_at:
                logger.debug("DNS 캐시 히트 host=%s", host)
                return ip
            del self._cache[host]

        logger.debug("DNS 캐시 미스 host=%s", host)
        try:
            ip = self._lookup(host)
        except OSError as e:  # gaierror(NXDOMAIN 등), timeout, 네트워크 오류
            logger.warning("DNS 조회 실패 host=%s: %s", host, e)
            return None
        self._cache[host] = (ip, self._clock() + self._ttl)
        return ip
