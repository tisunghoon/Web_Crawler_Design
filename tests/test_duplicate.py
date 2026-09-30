import hashlib
import logging

from hypothesis import assume, given
from hypothesis import strategies as st

from web_crawler.duplicate import DuplicateDetector, normalize


def test_new_then_duplicate():
    detector = DuplicateDetector()
    assert detector.check_and_register("http://a.com", "hello").verdict == "new"
    assert detector.check_and_register("http://b.com", "hello").verdict == "duplicate"


def test_different_body_is_new():
    detector = DuplicateDetector()
    detector.check_and_register("http://a.com", "hello")
    assert detector.check_and_register("http://b.com", "world").verdict == "new"


def test_strips_tags_and_surrounding_whitespace():
    detector = DuplicateDetector()
    detector.check_and_register("http://a.com", "hello")
    result = detector.check_and_register("http://b.com", "  <b>hello</b>\n")
    assert result.verdict == "duplicate"
    assert result.md5_hash == hashlib.md5(b"hello").hexdigest()


def test_empty_body_is_never_duplicate():
    detector = DuplicateDetector()
    assert detector.check_and_register("http://a.com", "   ").verdict == "empty"
    assert detector.check_and_register("http://b.com", "").verdict == "empty"


def test_logs_url_hash_and_verdict(caplog):
    caplog.set_level(logging.INFO)
    DuplicateDetector().check_and_register("http://a.com", "hello")
    assert "http://a.com" in caplog.text
    assert hashlib.md5(b"hello").hexdigest() in caplog.text
    assert "new" in caplog.text


# Feature: web-crawler-toy, Property 5: 같은 본문의 두 URL은 두 번째가 duplicate이고 해시가 같다
@given(st.text())
def test_same_body_is_duplicate_with_same_hash(body):
    assume(normalize(body))
    detector = DuplicateDetector()
    first = detector.check_and_register("http://a.com", body)
    second = detector.check_and_register("http://b.com", body)
    assert first.verdict == "new"
    assert second.verdict == "duplicate"
    assert first.md5_hash == second.md5_hash
