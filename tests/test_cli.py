import json

import pytest

from web_crawler.__main__ import main


@pytest.fixture
def server(httpserver):
    httpserver.expect_request("/robots.txt").respond_with_data("", status=404)
    httpserver.expect_request("/").respond_with_data(
        "<html><title>t</title><body>hello</body></html>", content_type="text/html"
    )
    return httpserver


def test_missing_seed_exits_with_usage_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_seed_without_scheme_returns_2(capsys):
    assert main(["example.com"]) == 2
    assert "오류" in capsys.readouterr().err


@pytest.mark.parametrize("flag, value", [("--max-depth", "0"), ("--max-pages", "0"), ("--delay", "61")])
def test_out_of_range_option_returns_2(flag, value, capsys):
    assert main(["http://example.com", flag, value]) == 2
    assert "오류" in capsys.readouterr().err


def test_runs_and_prints_summary(server, capsys):
    assert main([server.url_for("/"), "--delay", "0"]) == 0
    assert "수집한 페이지 수: 1" in capsys.readouterr().out


def test_output_option_writes_jsonl(server, tmp_path):
    out = tmp_path / "result.jsonl"
    assert main([server.url_for("/"), "--delay", "0", "--output", str(out)]) == 0
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["title"] for r in records] == ["t"]


def test_output_failure_returns_1(server, tmp_path):
    bad = tmp_path / "nodir" / "result.jsonl"
    assert main([server.url_for("/"), "--delay", "0", "--output", str(bad)]) == 1
