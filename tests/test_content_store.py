import json
import re

from hypothesis import given
from hypothesis import strategies as st

from web_crawler.content_store import MAX_FILE_RECORDS, ContentStore, utc_now_iso
from web_crawler.models import StoredPage

pages = st.builds(
    StoredPage,
    url=st.text(min_size=1),
    title=st.text(),
    body_text=st.text(),
    extracted_urls=st.lists(st.text()),
    crawled_at=st.text(),
    md5_hash=st.text(),
)


def make_page(url="http://a.com", body="본문"):
    return StoredPage(url, "제목", body, ["http://b.com"], "2024-01-01T00:00:00Z", "hash")


def test_get_missing_returns_none():
    assert ContentStore().get("http://none.com") is None


def test_all_urls_and_count():
    store = ContentStore()
    store.save(make_page("http://a.com"))
    store.save(make_page("http://b.com"))
    assert sorted(store.all_urls()) == ["http://a.com", "http://b.com"]
    assert store.count() == 2


def test_utc_now_iso_format():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_now_iso())


# Feature: web-crawler-toy, Property 9: save 후 get하면 모든 필드가 같은 객체를 반환한다
@given(pages)
def test_save_get_roundtrip(page):
    store = ContentStore()
    store.save(page)
    assert store.get(page.url) == page


# Feature: web-crawler-toy, Property 10: 같은 URL을 두 번 저장하면 마지막 값이 남는다
@given(pages, pages)
def test_overwrite_keeps_last(first, second):
    second.url = first.url
    store = ContentStore()
    store.save(first)
    store.save(second)
    assert store.get(first.url) == second
    assert store.count() == 1


def test_flush_writes_jsonl(tmp_path):
    store = ContentStore()
    store.save(make_page("http://a.com", "한글 본문"))
    path = tmp_path / "out.jsonl"
    assert store.flush_to_file(str(path)) is True
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["url"] == "http://a.com"
    assert record["body_text"] == "한글 본문"
    assert set(record) == {"url", "title", "body_text", "extracted_urls", "crawled_at", "md5_hash"}


def test_flush_limits_records(tmp_path):
    store = ContentStore()
    for i in range(MAX_FILE_RECORDS + 5):
        store.save(make_page(f"http://a.com/{i}"))
    path = tmp_path / "out.jsonl"
    assert store.flush_to_file(str(path)) is True
    assert len(path.read_text(encoding="utf-8").splitlines()) == MAX_FILE_RECORDS


def test_flush_failure_returns_false_and_logs(tmp_path, caplog):
    store = ContentStore()
    store.save(make_page())
    bad_path = tmp_path / "missing_dir" / "out.jsonl"
    assert store.flush_to_file(str(bad_path)) is False
    assert "파일 저장 실패" in caplog.text
