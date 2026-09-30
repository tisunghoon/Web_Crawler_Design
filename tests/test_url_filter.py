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
@given(st.text(), st.integers(min_value=0, max_value=20))
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
