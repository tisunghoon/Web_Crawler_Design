import logging
import time
from collections.abc import Callable
from urllib.parse import urlparse

from web_crawler.config import CrawlerConfig
from web_crawler.content_store import ContentStore, utc_now_iso
from web_crawler.dns_resolver import DNSResolver
from web_crawler.downloader import Downloader
from web_crawler.duplicate import DuplicateDetector
from web_crawler.frontier import URLFrontier
from web_crawler.models import CrawlSummary, StoredPage
from web_crawler.parser import ContentParser
from web_crawler.robots_cache import RobotsTxtCache
from web_crawler.url_filter import URLFilter
from web_crawler.visited_store import VisitedURLStore

logger = logging.getLogger(__name__)

SEED_PRIORITY = 1.0


def priority_for(depth: int) -> float:
    """얕은 깊이일수록 우선순위가 높아 BFS 레벨 순서가 유지된다."""
    return 1.0 / (1 + depth)


class Crawler:
    """Frontier에서 URL을 꺼내 다운로드·파싱·저장하고 새 링크를 되돌려 넣는 BFS 오케스트레이터."""

    def __init__(
        self,
        seed_urls: list[str],
        config: CrawlerConfig,
        resolver: DNSResolver,
        sleep: Callable[[float], None],
        clock: Callable[[], float],
    ) -> None:
        self.config = config
        self._clock = clock
        self.visited = VisitedURLStore()
        self.url_filter = URLFilter(self.visited, config.max_depth)
        self.frontier = URLFrontier(config.politeness_delay, clock=clock, sleep=sleep)
        self.resolver = resolver
        self.robots = RobotsTxtCache()
        self.downloader = Downloader(self.robots, self.visited, sleep=sleep)
        self.parser = ContentParser()
        self.detector = DuplicateDetector()
        self.store = ContentStore()
        self._skipped = 0
        self._duplicates = 0
        for url in seed_urls:
            self.frontier.push(url, SEED_PRIORITY, 0)

    @staticmethod
    def initialize(
        seed_urls: list[str],
        config: CrawlerConfig,
        *,
        resolver: DNSResolver | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> "Crawler":
        config.validate()
        if not seed_urls:
            raise ValueError("Seed URL 목록이 비어 있습니다.")

        valid: list[str] = []
        for url in dict.fromkeys(seed_urls):  # 순서를 유지한 중복 제거
            if url.startswith(("http://", "https://")):
                valid.append(url)
            else:
                logger.warning("http/https 스킴이 없는 Seed URL을 제외합니다: %s", url)
        if not valid:
            raise ValueError("유효한 Seed URL이 없습니다.")

        return Crawler(valid, config, resolver or DNSResolver(), sleep, clock)

    def run(self) -> CrawlSummary:
        started = self._clock()
        logger.info("크롤링 시작 max_depth=%s max_pages=%s", self.config.max_depth, self.config.max_pages)

        while not self.frontier.is_empty() and self.store.count() < self.config.max_pages:
            url, depth = self.frontier.pop()
            self._process(url, depth)

        save_failed = self.config.save_to_file and not self.store.flush_to_file(self.config.output_path)
        summary = CrawlSummary(
            total_pages=self.store.count(),
            skipped_urls=self._skipped,
            duplicate_count=self._duplicates,
            elapsed_seconds=self._clock() - started,
            save_failed=save_failed,
        )
        logger.info("크롤링 종료 %s", summary)
        self._print_summary(summary)
        return summary

    def _process(self, url: str, depth: int) -> None:
        allowed, _ = self.url_filter.is_allowed(url, depth)
        if not allowed:
            self._skipped += 1
            return
        host = urlparse(url).hostname
        if not host or self.resolver.resolve(host) is None:
            self._skipped += 1
            return

        result = self.downloader.download(url, depth)
        self._apply_crawl_delay(url)

        if result.status == "redirect":
            self._enqueue(result.redirect_url, depth)
        elif result.status == "ok":
            self._store_page(url, depth, result.html)
        else:
            self._skipped += 1

    def _apply_crawl_delay(self, url: str) -> None:
        parsed = urlparse(url)
        delay = self.robots.get_crawl_delay(parsed.netloc)
        if delay is not None and parsed.hostname:
            self.frontier.set_host_delay(parsed.hostname, delay)

    def _store_page(self, url: str, depth: int, html: str) -> None:
        parsed = self.parser.parse(html, url)
        verdict = self.detector.check_and_register(url, parsed.body_text)
        if verdict.verdict == "duplicate":
            self._duplicates += 1
            return

        self.store.save(
            StoredPage(
                url=url,
                title=parsed.title,
                body_text=parsed.body_text,
                extracted_urls=parsed.extracted_urls,
                crawled_at=utc_now_iso(),
                md5_hash=verdict.md5_hash,
            )
        )
        logger.info("페이지 저장 url=%s depth=%s", url, depth)
        if self.store.count() >= self.config.max_pages:
            return
        for link in parsed.extracted_urls:
            self._enqueue(link, depth + 1)

    def _enqueue(self, url: str, depth: int) -> None:
        allowed, _ = self.url_filter.is_allowed(url, depth)
        if allowed:
            self.frontier.push(url, priority_for(depth), depth)
        else:
            self._skipped += 1

    @staticmethod
    def _print_summary(summary: CrawlSummary) -> None:
        print("=== 크롤링 요약 ===")
        print(f"수집한 페이지 수: {summary.total_pages}")
        print(f"건너뛴 URL 수: {summary.skipped_urls}")
        print(f"중복 감지 수: {summary.duplicate_count}")
        print(f"소요 시간: {summary.elapsed_seconds:.2f}초")
        if summary.save_failed:
            print("파일 저장: 실패")
