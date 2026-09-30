import pytest
import requests
import responses

from web_crawler.robots_cache import RobotsTxtCache

ROBOTS = "http://a.com/robots.txt"


@responses.activate
def test_fetches_once_and_reuses_cache():
    responses.add(responses.GET, ROBOTS, body="User-agent: *\nDisallow: /private")
    cache = RobotsTxtCache()
    cache.is_allowed("http://a.com/x")
    cache.is_allowed("http://a.com/y")
    cache.get_crawl_delay("a.com")
    assert len(responses.calls) == 1


@responses.activate
def test_each_domain_is_fetched_separately():
    responses.add(responses.GET, ROBOTS, body="")
    responses.add(responses.GET, "https://b.com/robots.txt", body="")
    cache = RobotsTxtCache()
    cache.is_allowed("http://a.com/x")
    cache.is_allowed("https://b.com/x")
    assert [c.request.url for c in responses.calls] == [ROBOTS, "https://b.com/robots.txt"]


@responses.activate
@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://a.com/private", False),
        ("http://a.com/private/deep/page", False),
        ("http://a.com/privatex", False),  # prefix 매칭
        ("http://a.com/public", True),
        ("http://a.com/", True),
    ],
)
def test_disallow_uses_prefix_matching(url, expected):
    responses.add(responses.GET, ROBOTS, body="User-agent: *\nDisallow: /private")
    assert RobotsTxtCache().is_allowed(url) is expected


@responses.activate
def test_only_wildcard_section_applies():
    responses.add(responses.GET, ROBOTS, body="User-agent: Googlebot\nDisallow: /\n")
    assert RobotsTxtCache().is_allowed("http://a.com/x") is True


@responses.activate
def test_404_allows_everything_and_is_cached():
    responses.add(responses.GET, ROBOTS, status=404)
    cache = RobotsTxtCache()
    assert cache.is_allowed("http://a.com/anything") is True
    assert cache.is_allowed("http://a.com/other") is True
    assert cache.get_crawl_delay("a.com") is None
    assert len(responses.calls) == 1


@responses.activate
def test_request_failure_allows_everything(caplog):
    responses.add(responses.GET, ROBOTS, body=requests.ConnectionError("boom"))
    assert RobotsTxtCache().is_allowed("http://a.com/x") is True
    assert "robots.txt 요청 실패" in caplog.text


@responses.activate
@pytest.mark.parametrize("value, expected", [("5", 5.0), ("999", 300.0), ("300", 300.0)])
def test_crawl_delay_is_capped_at_300(value, expected):
    responses.add(responses.GET, ROBOTS, body=f"User-agent: *\nCrawl-delay: {value}")
    cache = RobotsTxtCache()
    cache.is_allowed("http://a.com/x")
    assert cache.get_crawl_delay("a.com") == expected


@responses.activate
def test_no_crawl_delay_returns_none():
    responses.add(responses.GET, ROBOTS, body="User-agent: *\nDisallow: /p")
    cache = RobotsTxtCache()
    cache.is_allowed("http://a.com/x")
    assert cache.get_crawl_delay("a.com") is None


def test_crawl_delay_for_unfetched_domain_is_none():
    assert RobotsTxtCache().get_crawl_delay("never.com") is None


def allowed(body, url):
    responses.add(responses.GET, ROBOTS, body=body)
    return RobotsTxtCache().is_allowed(url)


@responses.activate
@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://a.com/list?iframe=1", False),
        ("http://a.com/a/b?iframe=on&x=1", False),
        ("http://a.com/a/b?x=1&iframe=on", True),  # 패턴은 "?iframe=" 이므로 두 번째 파라미터는 해당 없음
        ("http://a.com/list?cate=1", True),
        ("http://a.com/my/x", False),
    ],
)
def test_star_wildcard_in_disallow(url, expected):
    assert allowed("User-agent: *\nDisallow: /my/\nDisallow: /*?iframe=*", url) is expected


@responses.activate
@pytest.mark.parametrize(
    "url, expected",
    [("http://a.com/doc.pdf", False), ("http://a.com/x/doc.pdf", False), ("http://a.com/doc.pdf?dl=1", True)],
)
def test_dollar_anchors_end_of_url(url, expected):
    assert allowed("User-agent: *\nDisallow: /*.pdf$", url) is expected


@responses.activate
@pytest.mark.parametrize(
    "url, expected",
    [
        ("http://a.com/private/x", False),
        ("http://a.com/private/public/x", True),  # 더 긴 Allow 패턴이 이긴다
        ("http://a.com/public", True),
    ],
)
def test_longest_match_wins(url, expected):
    body = "User-agent: *\nDisallow: /private\nAllow: /private/public"
    assert allowed(body, url) is expected


@responses.activate
def test_allow_wins_when_patterns_have_equal_length():
    assert allowed("User-agent: *\nDisallow: /page\nAllow: /page", "http://a.com/page") is True


@responses.activate
def test_empty_disallow_allows_everything():
    assert allowed("User-agent: *\nDisallow:", "http://a.com/anything") is True


@responses.activate
def test_comments_blank_lines_and_case_are_handled():
    body = "# 주석\n\nUSER-AGENT: *   # 모든 봇\ndisallow: /secret # 비공개\n"
    assert allowed(body, "http://a.com/secret/1") is False
    responses.reset()
    assert allowed(body, "http://a.com/open") is True


@responses.activate
def test_shared_rules_for_multiple_user_agent_lines():
    body = "User-agent: Googlebot\nUser-agent: *\nDisallow: /shared"
    assert allowed(body, "http://a.com/shared") is False


@responses.activate
def test_rules_from_multiple_wildcard_groups_are_merged():
    body = "User-agent: *\nDisallow: /one\n\nUser-agent: Other\nDisallow: /other\n\nUser-agent: *\nDisallow: /two"
    responses.add(responses.GET, ROBOTS, body=body)
    cache = RobotsTxtCache()
    assert cache.is_allowed("http://a.com/one") is False
    assert cache.is_allowed("http://a.com/two") is False
    assert cache.is_allowed("http://a.com/other") is True


@responses.activate
def test_decimal_crawl_delay_is_supported():
    responses.add(responses.GET, ROBOTS, body="User-agent: *\nCrawl-delay: 1.5")
    cache = RobotsTxtCache()
    cache.is_allowed("http://a.com/x")
    assert cache.get_crawl_delay("a.com") == 1.5


@responses.activate
def test_invalid_crawl_delay_is_ignored():
    responses.add(responses.GET, ROBOTS, body="User-agent: *\nCrawl-delay: soon")
    cache = RobotsTxtCache()
    cache.is_allowed("http://a.com/x")
    assert cache.get_crawl_delay("a.com") is None
