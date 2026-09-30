import pytest
import requests
import responses

from web_crawler.downloader import Downloader
from web_crawler.robots_cache import RobotsTxtCache
from web_crawler.visited_store import VisitedURLStore

URL = "http://a.com/page"
HTML = {"content_type": "text/html; charset=utf-8"}


@pytest.fixture
def sleeps():
    return []


@pytest.fixture
def visited():
    return VisitedURLStore()


@pytest.fixture
def downloader(visited, sleeps):
    responses.add(responses.GET, "http://a.com/robots.txt", status=404)
    return Downloader(RobotsTxtCache(), visited, sleep=sleeps.append)


def page_calls():
    return [c for c in responses.calls if c.request.url.endswith("/page")]


@responses.activate
def test_200_html_is_ok_and_visited(downloader, visited):
    responses.add(responses.GET, URL, body="<html>본문</html>", **HTML)
    result = downloader.download(URL, 0)
    assert (result.status, result.html) == ("ok", "<html>본문</html>")
    assert visited.contains(URL)


@responses.activate
def test_request_uses_30_second_timeout(downloader):
    responses.add(responses.GET, URL, body="x", **HTML)
    downloader.download(URL, 0)
    assert page_calls()[0].request.req_kwargs["timeout"] == 30


@responses.activate
def test_non_html_content_type_is_skipped(downloader):
    responses.add(responses.GET, URL, body="{}", content_type="application/json")
    result = downloader.download(URL, 0)
    assert (result.status, result.html) == ("skipped", None)


@responses.activate
def test_missing_content_type_is_skipped(downloader):
    responses.add(responses.GET, URL, body="x", content_type=None)
    assert "Content-Type" not in requests.get(URL).headers
    assert downloader.download(URL, 0).status == "skipped"


@responses.activate
@pytest.mark.parametrize("code", [301, 302])
def test_redirect_returns_absolute_location_and_marks_original_visited(downloader, visited, code):
    responses.add(responses.GET, URL, status=code, headers={"Location": "/moved"})
    result = downloader.download(URL, 0)
    assert (result.status, result.redirect_url) == ("redirect", "http://a.com/moved")
    assert visited.contains(URL)


@responses.activate
def test_redirect_without_location_is_error(downloader):
    responses.add(responses.GET, URL, status=302)
    assert downloader.download(URL, 0).status == "error"


@responses.activate
def test_more_than_five_redirects_is_error(visited, sleeps):
    responses.add(responses.GET, "http://a.com/robots.txt", status=404)
    downloader = Downloader(RobotsTxtCache(), visited, sleep=sleeps.append)
    for i in range(6):
        responses.add(
            responses.GET, f"http://a.com/r{i}", status=302, headers={"Location": f"/r{i + 1}"}
        )
    url = "http://a.com/r0"
    for _ in range(5):
        result = downloader.download(url, 0)
        assert result.status == "redirect"
        url = result.redirect_url
    final = downloader.download(url, 0)
    assert final.status == "error"
    assert "5회 초과" in final.error_reason


@responses.activate
def test_4xx_is_skipped_and_marked_visited(downloader, visited):
    responses.add(responses.GET, URL, status=404)
    result = downloader.download(URL, 0)
    assert (result.status, result.error_reason) == ("skipped", "HTTP 404")
    assert visited.contains(URL)
    assert len(page_calls()) == 1


@responses.activate
def test_5xx_retries_twice_with_5_second_interval(downloader, visited, sleeps):
    responses.add(responses.GET, URL, status=500)
    result = downloader.download(URL, 0)
    assert result.status == "error"
    assert len(page_calls()) == 3
    assert sleeps == [5, 5]
    assert visited.contains(URL)


@responses.activate
def test_success_after_retry(downloader, sleeps):
    responses.add(responses.GET, URL, status=503)
    responses.add(responses.GET, URL, body="ok", **HTML)
    assert downloader.download(URL, 0).status == "ok"
    assert len(page_calls()) == 2
    assert sleeps == [5]


@responses.activate
def test_timeout_is_retried_then_error(downloader, visited, sleeps):
    responses.add(responses.GET, URL, body=requests.Timeout("slow"))
    result = downloader.download(URL, 0)
    assert result.status == "error"
    assert len(page_calls()) == 3
    assert sleeps == [5, 5]
    assert visited.contains(URL)


@responses.activate
def test_robots_disallow_skips_without_requesting_page(visited, sleeps):
    responses.add(
        responses.GET, "http://a.com/robots.txt", body="User-agent: *\nDisallow: /page"
    )
    downloader = Downloader(RobotsTxtCache(), visited, sleep=sleeps.append)
    result = downloader.download(URL, 0)
    assert result.status == "skipped"
    assert page_calls() == []
