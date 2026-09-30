import dataclasses

import pytest

from web_crawler.config import CrawlerConfig
from web_crawler.models import CrawlSummary, ParsedPage


def test_defaults():
    config = CrawlerConfig()
    assert (config.max_depth, config.max_pages, config.politeness_delay) == (3, 1000, 1.0)
    assert config.save_to_file is False


@pytest.mark.parametrize("depth", [1, 10])
def test_depth_boundary_valid(depth):
    CrawlerConfig(max_depth=depth).validate()


@pytest.mark.parametrize("depth", [0, 11])
def test_depth_boundary_invalid(depth):
    with pytest.raises(ValueError):
        CrawlerConfig(max_depth=depth).validate()


@pytest.mark.parametrize("pages", [1, 100_000])
def test_pages_boundary_valid(pages):
    CrawlerConfig(max_pages=pages).validate()


@pytest.mark.parametrize("pages", [0, 100_001])
def test_pages_boundary_invalid(pages):
    with pytest.raises(ValueError):
        CrawlerConfig(max_pages=pages).validate()


@pytest.mark.parametrize("delay", [0, 60])
def test_delay_boundary_valid(delay):
    CrawlerConfig(politeness_delay=delay).validate()


@pytest.mark.parametrize("delay", [-0.1, 60.1])
def test_delay_boundary_invalid(delay):
    with pytest.raises(ValueError):
        CrawlerConfig(politeness_delay=delay).validate()


def test_config_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        CrawlerConfig().max_depth = 5


def test_models_defaults():
    assert ParsedPage(url="u", title="", body_text="").extracted_urls == []
    assert CrawlSummary(1, 0, 0, 0.1).save_failed is False


def test_default_user_agent_identifies_crawler():
    assert "web-crawler-toy" in CrawlerConfig().user_agent


@pytest.mark.parametrize("agent", ["", "   "])
def test_blank_user_agent_is_invalid(agent):
    with pytest.raises(ValueError):
        CrawlerConfig(user_agent=agent).validate()


def test_scope_defaults_are_restrictive():
    config = CrawlerConfig()
    assert config.allowed_domains == () and config.allow_any_domain is False


@pytest.mark.parametrize("domain", ["", "  ", "http://example.com", "example.com/path", "example.com:8080"])
def test_invalid_allowed_domain_is_rejected(domain):
    with pytest.raises(ValueError):
        CrawlerConfig(allowed_domains=(domain,)).validate()


def test_valid_allowed_domains_pass():
    CrawlerConfig(allowed_domains=("example.com", "shop.example.org")).validate()


def test_extractor_defaults_to_none_and_accepts_registered_names():
    assert CrawlerConfig().extractor is None
    CrawlerConfig(extractor="danawa").validate()


def test_unknown_extractor_is_rejected():
    with pytest.raises(ValueError):
        CrawlerConfig(extractor="nope").validate()
