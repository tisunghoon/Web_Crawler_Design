import pytest

from web_crawler.scope import Scope

SEEDS = ["https://shop.example.com/start"]


@pytest.mark.parametrize(
    "url, excluded",
    [
        ("https://shop.example.com/other?x=1", False),
        ("http://SHOP.Example.COM/", False),  # 대소문자 무시, 스킴 무관
        ("https://shop.example.com:8443/x", False),  # 포트 무관
        ("https://www.example.com/", True),  # 시드 호스트만 허용, 형제 호스트는 아님
        ("https://sub.shop.example.com/", True),
        ("https://other.org/", True),
    ],
)
def test_default_scope_is_seed_hosts_only(url, excluded):
    assert Scope(SEEDS).excludes(url) is excluded


def test_multiple_seed_hosts():
    scope = Scope(["http://a.com/", "http://b.com/"])
    assert not scope.excludes("http://a.com/x") and not scope.excludes("http://b.com/x")
    assert scope.excludes("http://c.com/")


@pytest.mark.parametrize(
    "url, excluded",
    [
        ("https://example.com/", False),
        ("https://www.example.com/", False),
        ("https://a.b.example.com/", False),
        ("https://notexample.com/", True),  # 접미사만 같은 다른 도메인
        ("https://example.com.evil.org/", True),
        ("https://other.org/", True),
    ],
)
def test_allowed_domain_includes_subdomains_but_not_lookalikes(url, excluded):
    scope = Scope(["http://seed.org/"], allowed_domains=("example.com",))
    assert scope.excludes(url) is excluded


def test_allowed_domain_normalizes_case_and_leading_dot():
    scope = Scope(["http://seed.org/"], allowed_domains=(".Example.COM",))
    assert not scope.excludes("https://www.example.com/")


def test_allow_any_domain():
    assert Scope(SEEDS, allow_any=True).excludes("https://other.org/") is False


@pytest.mark.parametrize("url", ["http://[bad", "not a url", "mailto:x@y.z", ""])
def test_urls_without_a_known_host_are_left_to_the_filter(url):
    assert Scope(SEEDS).excludes(url) is False


def test_malformed_seed_does_not_break_scope():
    scope = Scope(["http://[bad", "http://ok.com/"])
    assert not scope.excludes("http://ok.com/x")
    assert scope.excludes("http://other.com/")
