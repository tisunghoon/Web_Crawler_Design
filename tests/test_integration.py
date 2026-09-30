import json
from urllib.parse import urlparse

import pytest

from web_crawler.config import CrawlerConfig
from web_crawler.crawler import Crawler

HTML = "text/html; charset=utf-8"


def html(title, body, *links):
    anchors = "".join(f'<a href="{link}">link</a>' for link in links)
    return f"<html><head><title>{title}</title></head><body><p>{body}</p>{anchors}</body></html>"


@pytest.fixture
def site(httpserver):
    """
    /          -> /a /b /dup /gone /old /private/x mailto (nav은 본문에서 제거됨)
    /a         -> /a/deep
    /b, /dup   -> 같은 제목·본문 (/dup은 중복)
    /gone      -> 404
    /old       -> 302 /new
    /private/x -> robots.txt가 Disallow
    """

    def serve(path, body):
        httpserver.expect_request(path).respond_with_data(body, content_type=HTML)

    httpserver.expect_request("/robots.txt").respond_with_data("User-agent: *\nDisallow: /private")
    serve(
        "/",
        "<html><head><title>home</title></head><body><nav>MENU</nav><p>홈 페이지</p>"
        '<a href="/a">a</a><a href="/b">b</a><a href="/dup">dup</a><a href="/gone">gone</a>'
        '<a href="/old">old</a><a href="/private/x">private</a><a href="mailto:x@y.z">mail</a>'
        "</body></html>",
    )
    serve("/a", html("a", "페이지 a", "/a/deep"))
    serve("/a/deep", html("deep", "가장 깊은 페이지"))
    serve("/b", html("same", "같은 본문"))
    serve("/dup", html("same", "같은 본문"))
    serve("/new", html("new", "리다이렉트 도착 페이지"))
    serve("/private/x", html("private", "볼 수 없는 페이지"))
    httpserver.expect_request("/gone").respond_with_data("not found", status=404)
    httpserver.expect_request("/old").respond_with_data("", status=302, headers={"Location": "/new"})
    return httpserver


def crawl(site, **overrides):
    config = CrawlerConfig(politeness_delay=0, **overrides)
    crawler = Crawler.initialize([site.url_for("/")], config)
    return crawler, crawler.run()


def requested_paths(site):
    return [request.path for request, _ in site.log]


def test_full_crawl_summary_and_store(site):
    crawler, summary = crawl(site)

    assert summary.total_pages == 5
    assert summary.skipped_urls == 2  # /gone(404), /private/x(robots)
    assert summary.duplicate_count == 1  # /dup
    assert summary.save_failed is False
    assert summary.elapsed_seconds >= 0

    stored = sorted(urlparse(url).path for url in crawler.store.all_urls())
    assert stored == ["/", "/a", "/a/deep", "/b", "/new"]
    assert crawler.store.get(site.url_for("/dup")) is None
    assert crawler.store.get(site.url_for("/private/x")) is None


def test_stored_page_content(site):
    crawler, _ = crawl(site)
    home = crawler.store.get(site.url_for("/"))

    assert home.title == "home"
    assert "홈 페이지" in home.body_text
    assert "MENU" not in home.body_text
    assert sorted(home.extracted_urls) == sorted(
        site.url_for(p) for p in ["/a", "/b", "/dup", "/gone", "/old", "/private/x"]
    )
    assert home.crawled_at.endswith("Z") and len(home.crawled_at) == 20
    assert len(home.md5_hash) == 32


def test_requests_follow_bfs_depth_order(site):
    crawl(site)
    # robots.txt는 도메인당 한 번, 깊이 1이 모두 끝난 뒤에 깊이 2(/a/deep)를 요청하고,
    # robots가 막은 /private/x는 요청하지 않는다.
    assert requested_paths(site) == [
        "/robots.txt", "/", "/a", "/b", "/dup", "/gone", "/old", "/new", "/a/deep",
    ]


def test_max_pages_stops_crawl(site):
    crawler, summary = crawl(site, max_pages=3)
    assert summary.total_pages == crawler.store.count() == 3
    assert "/a/deep" not in requested_paths(site)


def test_max_depth_limits_crawl(site):
    _, summary = crawl(site, max_depth=1)
    assert "/a/deep" not in requested_paths(site)
    assert summary.total_pages == 4  # /, /a, /b, /new


def test_summary_printed_and_file_saved(site, tmp_path, capsys):
    out = tmp_path / "result.jsonl"
    _, summary = crawl(site, save_to_file=True, output_path=str(out))

    printed = capsys.readouterr().out
    assert "수집한 페이지 수: 5" in printed
    assert "건너뛴 URL 수: 2" in printed
    assert "중복 감지 수: 1" in printed

    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(records) == summary.total_pages
    assert {r["title"] for r in records} == {"home", "a", "deep", "same", "new"}
