import logging

from hypothesis import given
from hypothesis import strategies as st

from web_crawler.parser import ContentParser

BASE = "http://example.com/dir/page.html"


def parse(html, base=BASE):
    return ContentParser().parse(html, base)


def test_extracts_title():
    assert parse("<html><head><title> 제목 </title></head></html>").title == "제목"


def test_missing_or_empty_title_is_empty_string():
    assert parse("<p>x</p>").title == ""
    assert parse("<title></title>").title == ""


def test_body_text_removes_noise_tags():
    html = (
        "<body><nav>메뉴</nav><script>var a=1;</script><style>p{}</style>"
        "<p>첫째</p>\n<div>둘째</div><div> 셋째 </div><footer>푸터</footer></body>"
    )
    assert parse(html).body_text == "첫째 둘째 셋째"


def test_links_inside_removed_tags_are_still_extracted():
    html = '<nav><a href="http://a.com/menu">m</a></nav><a href="http://a.com/x">x</a>'
    assert parse(html).extracted_urls == ["http://a.com/menu", "http://a.com/x"]


def test_extracts_absolute_and_resolves_relative():
    html = (
        '<a href="https://a.com/1">1</a><a href="/root">2</a>'
        '<a href="./same">3</a><a href="../up">4</a>'
    )
    assert parse(html).extracted_urls == [
        "https://a.com/1",
        "http://example.com/root",
        "http://example.com/dir/same",
        "http://example.com/up",
    ]


def test_excludes_forbidden_and_unsupported_hrefs():
    html = (
        '<a href="javascript:void(0)">a</a><a href="mailto:a@b.c">b</a>'
        '<a href="#top">c</a><a href="page.html">d</a><a href="ftp://a.com/f">e</a><a>f</a>'
    )
    assert parse(html).extracted_urls == []


def test_relative_without_base_url_is_excluded():
    html = '<a href="/x">x</a><a href="http://a.com/y">y</a>'
    page = ContentParser().parse(html)
    assert page.extracted_urls == ["http://a.com/y"]
    assert page.url == ""


def test_url_field_is_base_url_as_given():
    assert parse("<p>x</p>").url == BASE


def test_parse_failure_returns_empty_page_and_logs(caplog):
    caplog.set_level(logging.ERROR)
    page = ContentParser().parse(None, BASE)  # type: ignore[arg-type]
    assert page.__dict__ == {"url": BASE, "title": "", "body_text": "", "extracted_urls": []}
    assert "HTML 파싱 실패" in caplog.text


hrefs = st.one_of(
    st.from_regex(r"https?://[a-z]{1,8}\.com/[a-z0-9]{0,8}", fullmatch=True),
    st.from_regex(r"(/|\./|\.\./)[a-z0-9/]{0,10}", fullmatch=True),
    st.from_regex(r"(javascript:|mailto:|#)[a-z0-9(). @]{0,10}", fullmatch=True),
    st.from_regex(r"[a-z0-9]{1,8}\.html", fullmatch=True),
)


# Feature: web-crawler-toy, Property 4: 추출된 URL은 모두 절대 http(s) URL이고 금지 스킴은 없다
@given(st.lists(hrefs, max_size=10))
def test_extracted_urls_are_absolute_and_clean(links):
    html = "".join(f'<a href="{h}">x</a>' for h in links)
    for url in parse(html).extracted_urls:
        assert url.startswith(("http://", "https://"))
        assert not url.startswith(("javascript:", "mailto:", "#"))
