from hypothesis import given
from hypothesis import strategies as st

from web_crawler.frontier import URLFrontier


class FakeTime:
    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def make_frontier(delay=1.0):
    t = FakeTime()
    return URLFrontier(delay, clock=t.clock, sleep=t.sleep), t


def test_empty_frontier():
    frontier, _ = make_frontier()
    assert frontier.pop() is None
    assert frontier.is_empty() is True


def test_push_and_pop_returns_url_and_depth():
    frontier, _ = make_frontier()
    assert frontier.push("http://a.com/1", 1.0, 2) is True
    assert frontier.is_empty() is False
    assert frontier.pop() == ("http://a.com/1", 2)
    assert frontier.is_empty() is True


def test_duplicate_push_rejected_even_after_pop():
    frontier, _ = make_frontier(0)
    assert frontier.push("http://a.com/1", 1.0, 0) is True
    assert frontier.push("http://a.com/1", 0.5, 3) is False
    frontier.pop()
    assert frontier.push("http://a.com/1", 1.0, 0) is False


def test_higher_priority_first_and_ties_are_fifo():
    frontier, _ = make_frontier(0)
    frontier.push("http://a.com/low", 0.2, 1)
    frontier.push("http://a.com/first", 0.5, 1)
    frontier.push("http://a.com/second", 0.5, 1)
    frontier.push("http://a.com/top", 1.0, 0)
    order = [frontier.pop()[0] for _ in range(4)]
    assert order == [
        "http://a.com/top",
        "http://a.com/first",
        "http://a.com/second",
        "http://a.com/low",
    ]


def test_first_request_to_host_does_not_wait():
    frontier, t = make_frontier(5)
    frontier.push("http://a.com/1", 1.0, 0)
    frontier.pop()
    assert t.sleeps == []


def test_same_host_waits_remaining_delay():
    frontier, t = make_frontier(5)
    frontier.push("http://a.com/1", 1.0, 0)
    frontier.push("http://a.com/2", 0.9, 0)
    frontier.pop()
    t.now += 2
    frontier.pop()
    assert t.sleeps == [3]


def test_no_wait_when_delay_already_elapsed():
    frontier, t = make_frontier(5)
    frontier.push("http://a.com/1", 1.0, 0)
    frontier.push("http://a.com/2", 0.9, 0)
    frontier.pop()
    t.now += 5
    frontier.pop()
    assert t.sleeps == []


def test_different_hosts_do_not_wait_for_each_other():
    frontier, t = make_frontier(5)
    frontier.push("http://a.com/1", 1.0, 0)
    frontier.push("http://b.com/1", 0.9, 0)
    frontier.pop()
    frontier.pop()
    assert t.sleeps == []


def test_host_delay_overrides_default():
    frontier, t = make_frontier(1)
    frontier.set_host_delay("A.com", 10)
    frontier.push("http://a.com/1", 1.0, 0)
    frontier.push("http://a.com/2", 0.9, 0)
    frontier.push("http://b.com/1", 0.8, 0)
    frontier.push("http://b.com/2", 0.7, 0)
    for _ in range(4):
        frontier.pop()
    assert t.sleeps == [10, 1]


def test_zero_host_delay_disables_wait():
    frontier, t = make_frontier(5)
    frontier.set_host_delay("a.com", 0)
    frontier.push("http://a.com/1", 1.0, 0)
    frontier.push("http://a.com/2", 0.9, 0)
    frontier.pop()
    frontier.pop()
    assert t.sleeps == []


urls = st.from_regex(r"https?://[a-z]{1,5}\.com/[a-z0-9]{0,5}", fullmatch=True)


# Feature: web-crawler-toy, Property 1: 같은 URL을 여러 번 삽입해도 한 번만 들어간다
@given(st.lists(urls, min_size=1))
def test_duplicate_push_is_idempotent(url_list):
    frontier, _ = make_frontier(0)
    accepted = [frontier.push(u, 1.0, 0) for u in url_list + url_list]
    assert accepted.count(True) == len(set(url_list))
    popped = []
    while (item := frontier.pop()) is not None:
        popped.append(item[0])
    assert sorted(popped) == sorted(set(url_list))


# Feature: web-crawler-toy, Property 2: pop 순서는 우선순위 내림차순(동점은 삽입 순)을 지킨다
@given(st.lists(st.tuples(urls, st.floats(min_value=0, max_value=1)), min_size=1, unique_by=lambda x: x[0]))
def test_pop_order_respects_priority(entries):
    frontier, _ = make_frontier(0)
    for url, priority in entries:
        frontier.push(url, priority, 0)
    expected = [u for u, _ in sorted(entries, key=lambda e: -e[1])]  # 안정 정렬 = 동점 FIFO
    popped = [frontier.pop()[0] for _ in entries]
    assert popped == expected
