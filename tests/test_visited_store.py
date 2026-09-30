from hypothesis import given
from hypothesis import strategies as st

from web_crawler.visited_store import VisitedURLStore


def test_empty_store():
    store = VisitedURLStore()
    assert store.count() == 0
    assert store.contains("http://a.com") is False


def test_add_then_contains():
    store = VisitedURLStore()
    store.add("http://a.com")
    assert store.contains("http://a.com") is True
    assert store.contains("http://b.com") is False


# Feature: web-crawler-toy, Property 8: 같은 URL을 여러 번 add해도 count는 고유 URL 수와 같다
@given(st.lists(st.text(min_size=1), min_size=1))
def test_add_is_idempotent(urls):
    store = VisitedURLStore()
    for url in urls + urls:
        store.add(url)
    assert store.count() == len(set(urls))
    assert all(store.contains(url) for url in urls)
