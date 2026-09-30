from collections.abc import Iterable
from urllib.parse import urlparse


def _hostname(url: str) -> str | None:
    try:
        return (urlparse(url).hostname or "").lower() or None
    except ValueError:
        return None


class Scope:
    """크롤링 범위. 기본은 시드와 정확히 같은 호스트만 허용하고,
    허용 도메인은 그 도메인과 모든 하위 도메인을 허용한다."""

    def __init__(
        self,
        seed_urls: Iterable[str],
        allowed_domains: Iterable[str] = (),
        allow_any: bool = False,
    ) -> None:
        self._allow_any = allow_any
        self._seed_hosts = {host for url in seed_urls if (host := _hostname(url))}
        self._domains = tuple(d.strip().lower().lstrip(".") for d in allowed_domains)

    def excludes(self, url: str) -> bool:
        """호스트를 알 수 있는데 허용 범위 밖이면 True.
        호스트를 알 수 없는 URL(형식 오류 등)은 범위 문제가 아니므로 False로 두고 URLFilter가 거부하게 한다."""
        if self._allow_any:
            return False
        host = _hostname(url)
        if host is None:
            return False
        allowed = host in self._seed_hosts or any(
            host == domain or host.endswith("." + domain) for domain in self._domains
        )
        return not allowed
