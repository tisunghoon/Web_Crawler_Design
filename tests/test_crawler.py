import json
import socket

import pytest
import responses
from hypothesis import assume, given
from hypothesis import strategies as st

from web_crawler.config import CrawlerConfig
from web_crawler.crawler import Crawler, priority_for
from web_crawler.dns_resolver import DNSResolver

HTML = {"content_type": "text/html"}


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def ok_resolver():
    return DNSResolver(lookup=lambda host: "127.0.0.1")


def make_crawler(seeds, config=None, resolver=None, fake=None):
    fake = fake or FakeTime()
    config = config or CrawlerConfig(politeness_delay=0)
    crawler = Crawler.initialize(
        seeds, config, resolver=resolver or ok_resolver(), sleep=fake.sleep, clock=fake.clock
    )
    return crawler, fake


def page(path, *links, body=None, title=None):
    hrefs = "".join(f'<a href="{link}">l</a>' for link in links)
    html = f"<html><title>{title or path}</title><body><p>{body or 'content ' + path}</p>{hrefs}</body></html>"
    responses.add(responses.GET, f"http://a.com{path}", body=html, **HTML)


def robots(body="", status=200):
    responses.add(responses.GET, "http://a.com/robots.txt", body=body, status=status)


def fetched_paths():
    return [
        c.request.url.removeprefix("http://a.com")
        for c in responses.calls
        if not c.request.url.endswith("/robots.txt")
    ]


# ---------- initialize ----------


def test_empty_seed_raises():
    with pytest.raises(ValueError):
        Crawler.initialize([], CrawlerConfig())


def test_invalid_config_raises():
    with pytest.raises(ValueError):
        Crawler.initialize(["http://a.com"], CrawlerConfig(max_depth=0))


def test_seed_without_scheme_is_excluded_with_warning(caplog):
    crawler, _ = make_crawler(["a.com", "ftp://b.com", "http://ok.com/"])
    assert crawler.frontier.pop() == ("http://ok.com/", 0)
    assert crawler.frontier.is_empty()
    assert "a.com" in caplog.text and "ftp://b.com" in caplog.text


def test_all_invalid_seeds_raise():
    with pytest.raises(ValueError):
        Crawler.initialize(["a.com", "mailto:x"], CrawlerConfig())


def test_default_config_values():
    config = CrawlerConfig()
    assert (config.max_depth, config.max_pages, config.politeness_delay) == (3, 1000, 1.0)


def test_priority_prefers_shallow_depth():
    assert priority_for(0) > priority_for(1) > priority_for(5) > 0


valid_urls = st.from_regex(r"https?://[a-z]{1,5}\.com/[a-z0-9]{0,4}", fullmatch=True)


# Feature: web-crawler-toy, Property 11: 중복을 포함한 seed 목록에서 고유 유효 URL 수만큼만 프론티어에 들어간다
@given(st.lists(st.one_of(valid_urls, st.text(max_size=8)), min_size=1, max_size=15))
def test_initialize_deduplicates_seeds(seeds):
    expected = {s for s in seeds if s.startswith(("http://", "https://"))}
    assume(expected)
    crawler, _ = make_crawler(seeds + seeds)
    popped = []
    while (item := crawler.frontier.pop()) is not None:
        popped.append(item[0])
    assert len(popped) == len(expected)
    assert set(popped) == expected


# ---------- run ----------


@responses.activate
def test_bfs_visits_level_by_level():
    robots(status=404)
    page("/", "/a", "/b")
    page("/a", "/a1", "/a2")
    page("/b", "/b1")
    for leaf in ("/a1", "/a2", "/b1"):
        page(leaf)
    crawler, _ = make_crawler(["http://a.com/"])
    summary = crawler.run()
    assert fetched_paths() == ["/", "/a", "/b", "/a1", "/a2", "/b1"]
    assert summary.total_pages == 6


@responses.activate
def test_max_depth_limits_crawl():
    robots(status=404)
    page("/", "/a")
    page("/a", "/deep")
    page("/deep")
    crawler, _ = make_crawler(["http://a.com/"], CrawlerConfig(max_depth=1, politeness_delay=0))
    summary = crawler.run()
    assert "/deep" not in fetched_paths()
    assert summary.total_pages == 2
    assert summary.skipped_urls == 1  # /deep: 깊이 초과


@responses.activate
def test_stops_when_max_pages_reached():
    robots(status=404)
    page("/", "/a", "/b")
    page("/a")
    page("/b")
    crawler, _ = make_crawler(["http://a.com/"], CrawlerConfig(max_pages=2, politeness_delay=0))
    summary = crawler.run()
    assert summary.total_pages == 2
    assert fetched_paths() == ["/", "/a"]


@responses.activate
def test_stops_normally_when_frontier_is_empty():
    robots(status=404)
    page("/")
    crawler, _ = make_crawler(["http://a.com/"])
    assert crawler.run().total_pages == 1
    assert crawler.frontier.is_empty()


@responses.activate
def test_duplicate_content_is_not_stored_and_its_links_not_followed():
    robots(status=404)
    page("/", "/a", "/b")
    page("/a", "/from-a", body="same", title="t")
    page("/b", "/from-b", body="same", title="t")
    page("/from-a")
    page("/from-b")
    crawler, _ = make_crawler(["http://a.com/"])
    summary = crawler.run()
    assert summary.duplicate_count == 1
    assert summary.total_pages == 3  # /, /a, /from-a (/b는 중복, /from-b는 따라가지 않음)
    assert crawler.store.get("http://a.com/b") is None
    assert "/from-b" not in fetched_paths()


@responses.activate
def test_skipped_counts_filter_and_downloader():
    robots("User-agent: *\nDisallow: /private")
    page("/", "/missing", "/private", "mailto:x", "/a", "/a")
    page("/a")
    responses.add(responses.GET, "http://a.com/missing", status=404)
    crawler, _ = make_crawler(["http://a.com/"])
    summary = crawler.run()
    assert summary.total_pages == 2
    assert summary.skipped_urls == 2  # /missing(404), /private(robots)


@responses.activate
def test_dns_failure_skips_url():
    def lookup(host):
        raise socket.gaierror("NXDOMAIN")

    robots(status=404)
    crawler, _ = make_crawler(["http://a.com/"], resolver=DNSResolver(lookup=lookup))
    summary = crawler.run()
    assert (summary.total_pages, summary.skipped_urls) == (0, 1)
    assert len(responses.calls) == 0


@responses.activate
def test_redirect_target_is_crawled_at_same_depth():
    robots(status=404)
    responses.add(responses.GET, "http://a.com/old", status=301, headers={"Location": "/new"})
    page("/new")
    crawler, _ = make_crawler(["http://a.com/old"])
    summary = crawler.run()
    assert summary.total_pages == 1
    assert crawler.store.get("http://a.com/new") is not None
    assert crawler.visited.contains("http://a.com/old")


@responses.activate
def test_robots_crawl_delay_overrides_default_politeness():
    robots("User-agent: *\nCrawl-delay: 7")
    page("/", "/x")
    page("/x")
    fake = FakeTime()
    crawler, _ = make_crawler(["http://a.com/"], CrawlerConfig(politeness_delay=1), fake=fake)
    crawler.run()
    assert fake.sleeps == [7]


@responses.activate
def test_summary_is_printed_to_stdout(capsys):
    robots(status=404)
    page("/")
    fake = FakeTime()
    crawler, _ = make_crawler(["http://a.com/"], fake=fake)
    summary = crawler.run()
    out = capsys.readouterr().out
    assert "수집한 페이지 수: 1" in out
    assert "건너뛴 URL 수: 0" in out
    assert "중복 감지 수: 0" in out
    assert "소요 시간:" in out
    assert summary.elapsed_seconds == 0


@responses.activate
def test_save_to_file_writes_jsonl(tmp_path):
    robots(status=404)
    page("/", "/a")
    page("/a")
    out = tmp_path / "crawl.jsonl"
    config = CrawlerConfig(politeness_delay=0, save_to_file=True, output_path=str(out))
    crawler, _ = make_crawler(["http://a.com/"], config)
    summary = crawler.run()
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert sorted(r["url"] for r in records) == ["http://a.com/", "http://a.com/a"]
    assert summary.save_failed is False


@responses.activate
def test_save_failure_is_reflected_in_summary(tmp_path, capsys):
    robots(status=404)
    page("/")
    config = CrawlerConfig(
        politeness_delay=0, save_to_file=True, output_path=str(tmp_path / "nodir" / "x.jsonl")
    )
    crawler, _ = make_crawler(["http://a.com/"], config)
    summary = crawler.run()
    assert summary.save_failed is True
    assert summary.total_pages == 1
    assert "파일 저장: 실패" in capsys.readouterr().out


@responses.activate
def test_malformed_link_is_skipped_and_crawl_continues():
    robots(status=404)
    page("/", "http://[bad", "/ok")
    page("/ok")
    crawler, _ = make_crawler(["http://a.com/"])
    summary = crawler.run()
    assert summary.total_pages == 2
    assert summary.skipped_urls == 1


@responses.activate
def test_malformed_seed_is_skipped_and_crawl_continues():
    robots(status=404)
    page("/")
    crawler, _ = make_crawler(["http://[bad", "http://a.com/"])
    summary = crawler.run()
    assert summary.total_pages == 1
    assert summary.skipped_urls == 1


@responses.activate
def test_malformed_redirect_location_does_not_stop_crawl():
    robots(status=404)
    page("/", "/bad-redirect", "/ok")
    page("/ok")
    responses.add(responses.GET, "http://a.com/bad-redirect", status=302, headers={"Location": "http://[bad"})
    crawler, _ = make_crawler(["http://a.com/"])
    summary = crawler.run()
    assert summary.total_pages == 2
    assert summary.skipped_urls == 1


@responses.activate
def test_unexpected_error_on_one_url_is_logged_and_crawl_continues(caplog):
    robots(status=404)
    page("/", "/boom", "/ok")
    page("/boom")
    page("/ok")
    crawler, _ = make_crawler(["http://a.com/"])
    original = crawler.parser.parse

    def flaky(html, base_url=None):
        if base_url and base_url.endswith("/boom"):
            raise RuntimeError("예상 못 한 오류")
        return original(html, base_url)

    crawler.parser.parse = flaky
    summary = crawler.run()
    assert summary.total_pages == 2  # /, /ok
    assert summary.skipped_urls == 1
    assert "예상 못 한 오류" in caplog.text and "http://a.com/boom" in caplog.text
