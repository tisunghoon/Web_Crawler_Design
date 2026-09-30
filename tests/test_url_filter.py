import logging

import pytest
from hypothesis import given
from hypothesis import strategies as st

from web_crawler.url_filter import URLFilter
from web_crawler.visited_store import VisitedURLStore


def make_filter(max_depth=3):
    visited = VisitedURLStore()
    return URLFilter(visited, max_depth), visited


def test_allows_normal_url():
    assert make_filter()[0].is_allowed("http://a.com/x", 1) == (True, None)


@pytest.mark.parametrize("url", ["ftp://a.com/x", "javascript:alert(1)", "//a.com/x", "a.com"])
def test_rejects_bad_scheme(url):
    assert make_filter()[0].is_allowed(url, 0) == (False, "스킴 오류")


def test_length_boundary():
    url_ok = "http://a.com/" + "a" * (2048 - len("http://a.com/"))
    assert len(url_ok) == 2048
    assert make_filter()[0].is_allowed(url_ok, 0)[0] is True
    assert make_filter()[0].is_allowed(url_ok + "a", 0) == (False, "길이 초과")


def test_depth_boundary():
    url_filter, _ = make_filter(max_depth=3)
    assert url_filter.is_allowed("http://a.com", 3)[0] is True
    assert url_filter.is_allowed("http://a.com", 4) == (False, "깊이 초과")


def test_rejects_repeated_segments_case_insensitive():
    assert make_filter()[0].is_allowed("http://a.com/a/b/A/b/a", 0) == (False, "경로 반복")


def test_two_repeats_are_allowed():
    assert make_filter()[0].is_allowed("http://a.com/a/b/a/b", 0)[0] is True


def test_rejects_visited():
    url_filter, visited = make_filter()
    visited.add("http://a.com/x")
    assert url_filter.is_allowed("http://a.com/x", 0) == (False, "이미 방문")


def test_multiple_violations_report_first_only(caplog):
    url_filter, visited = make_filter(max_depth=1)
    url = "ftp://a.com/a/a/a"
    visited.add(url)
    assert url_filter.is_allowed(url, 9) == (False, "스킴 오류")
    assert caplog.text.count("사유=") == 1
    assert "스킴 오류" in caplog.text and "깊이 초과" not in caplog.text


def test_rejection_is_logged(caplog):
    caplog.set_level(logging.WARNING)
    make_filter(max_depth=1)[0].is_allowed("http://a.com", 5)
    assert "http://a.com" in caplog.text and "깊이 초과" in caplog.text


# Feature: web-crawler-toy, Property 6: 거부하면 사유 문자열이, 허용하면 None이 함께 반환된다
malformed = st.from_regex(r"https?://\[[a-z0-9:]{0,5}", fullmatch=True)


@given(st.one_of(st.text(), malformed), st.integers(min_value=0, max_value=20))
def test_result_and_reason_are_consistent(url, depth):
    allowed, reason = make_filter()[0].is_allowed(url, depth)
    if allowed:
        assert reason is None
    else:
        assert isinstance(reason, str) and reason


segment = st.from_regex(r"[a-zA-Z0-9]{1,5}", fullmatch=True)


# Feature: web-crawler-toy, Property 7: 같은 세그먼트가 대소문자 무시 3회 이상이면 거부한다
@given(st.lists(segment, max_size=4), segment)
def test_repeated_segment_is_rejected(others, seg):
    path = "/".join(others + [seg, seg.upper(), seg.lower()])
    allowed, reason = make_filter(max_depth=10)[0].is_allowed(f"http://a.com/{path}", 0)
    assert (allowed, reason) == (False, "경로 반복")


@pytest.mark.parametrize("url", ["http://[bad", "http://[::1", "https://[abc]x"])
def test_unparseable_url_is_rejected_not_raised(url):
    assert make_filter()[0].is_allowed(url, 0) == (False, "URL 형식 오류")


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.com\\@a.com/x",  # urlparse는 a.com, urllib3(requests)는 evil.com
        "http://127.0.0.1:8080\\@localhost:8080/x",
        "http://evil.com\\@a.com@",
        "http:///a.com/",
        "http://",
    ],
)
def test_host_confusing_urls_are_rejected(url):
    assert make_filter()[0].is_allowed(url, 0) == (False, "URL 형식 오류")


@pytest.mark.parametrize(
    "url",
    [
        "http://a.com/x",
        "http://A.COM/x",
        "http://user:pw@a.com/x",
        "http://a.com@evil.com/",  # 두 파서 모두 evil.com. 호스트 판정이 같으면 필터는 통과시키고 범위가 걸러낸다
        "http://a.com#@evil.com/",  # 호스트는 a.com. 어긋나 보이지만 일치하므로 통과해야 한다
        "http://a.com%40evil.com/",
        "HTTP://a.com/x",
        "http://[::1]:8080/x",
        "http://[2001:db8::1]/x",
        "http://bücher.de/x",
        "http://a.com:8080/x",
    ],
)
def test_consistent_hosts_are_not_rejected_as_malformed(url):
    assert make_filter()[0].is_allowed(url, 0) == (True, None)


_hosts = st.sampled_from(["a.com", "evil.com", "127.0.0.1:80", "localhost", "[::1]", "b\u00fccher.de", "x"])
_separators = st.sampled_from(["\\@", "@", "\\", "\\\\", ":", "#", "?", "%5c@", " @", "\t@", ""])
_paths = st.sampled_from(["", "/", "/x", "/a@b"])
# 무작위 문자열만으로는 "host\\@host" 같은 혼동 조합이 거의 나오지 않아 위험한 조각을 직접 조립한다
hostile = st.one_of(
    st.builds(lambda a, sep, b, path: f"http://{a}{sep}{b}{path}", _hosts, _separators, _hosts, _paths),
    st.text(alphabet="ab.:/@\\[]-%1 #?\t\n\x00\uff41\u3002", max_size=25).map(lambda tail: "http://" + tail),
)


# 필터를 통과한 URL은 requests가 실제로 접속할 호스트와 urlparse가 읽은 호스트가 같아야 한다 (전송 없이 준비만 한다)
@given(hostile)
def test_allowed_urls_have_the_same_host_for_urlparse_and_requests(url):
    from urllib.parse import urlparse

    import requests
    from urllib3.util import parse_url

    from web_crawler.url_filter import _normalized

    allowed, _ = make_filter()[0].is_allowed(url, 0)
    if not allowed:
        return
    try:
        prepared = requests.Request("GET", url).prepare().url
    except requests.RequestException:
        return  # 요청이 만들어지지 않으면 어디에도 접속하지 않는다
    connect_host = _normalized(parse_url(prepared).host)  # requests가 실제로 접속하는 호스트
    assert connect_host == _normalized(urlparse(url).hostname)
