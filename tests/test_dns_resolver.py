import socket

from hypothesis import given
from hypothesis import strategies as st

from web_crawler.dns_resolver import DEFAULT_TTL, DNSResolver


class FakeLookup:
    def __init__(self):
        self.calls = 0

    def __call__(self, host):
        self.calls += 1
        return f"10.0.0.{self.calls}"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_default_ttl_is_600():
    assert DEFAULT_TTL == 600


def test_cache_hit_skips_lookup():
    lookup, clock = FakeLookup(), FakeClock()
    resolver = DNSResolver(lookup=lookup, clock=clock)
    assert resolver.resolve("a.com") == "10.0.0.1"
    clock.now = 599
    assert resolver.resolve("a.com") == "10.0.0.1"
    assert lookup.calls == 1


def test_hosts_are_cached_separately():
    lookup = FakeLookup()
    resolver = DNSResolver(lookup=lookup)
    resolver.resolve("a.com")
    resolver.resolve("b.com")
    assert lookup.calls == 2


def test_expired_record_is_looked_up_again():
    lookup, clock = FakeLookup(), FakeClock()
    resolver = DNSResolver(lookup=lookup, clock=clock)
    resolver.resolve("a.com")
    clock.now = 600
    assert resolver.resolve("a.com") == "10.0.0.2"
    assert lookup.calls == 2


def test_lookup_failure_returns_none_and_is_not_cached(caplog):
    calls = []

    def failing(host):
        calls.append(host)
        raise socket.gaierror("NXDOMAIN")

    resolver = DNSResolver(lookup=failing)
    assert resolver.resolve("nope.invalid") is None
    assert resolver.resolve("nope.invalid") is None
    assert len(calls) == 2
    assert "DNS 조회 실패" in caplog.text


def test_timeout_returns_none():
    def timing_out(host):
        raise socket.timeout("timed out")

    assert DNSResolver(lookup=timing_out).resolve("a.com") is None


# Feature: web-crawler-toy, Property 3: TTL이 만료되면 캐시를 쓰지 않고 새로 조회한다
@given(st.text(min_size=1), st.floats(min_value=0, max_value=1e6))
def test_expired_ttl_triggers_new_lookup(host, ttl):
    lookup, clock = FakeLookup(), FakeClock()
    resolver = DNSResolver(ttl=ttl, lookup=lookup, clock=clock)
    first = resolver.resolve(host)
    clock.now = ttl
    second = resolver.resolve(host)
    assert lookup.calls == 2
    assert first != second
