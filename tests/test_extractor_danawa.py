from pathlib import Path

import pytest

from web_crawler.extractors import EXTRACTORS
from web_crawler.extractors.danawa import extract_products
from web_crawler.models import Product

SAMPLE = (Path(__file__).parent / "fixtures" / "danawa_list_sample.html").read_text(encoding="utf-8")
BASE = "https://prod.danawa.com/list/?cate=112758"


def by_pcode(products):
    return {p.pcode: p for p in products}


def test_registered_under_its_name():
    assert EXTRACTORS["danawa"] is extract_products


def test_extracts_name_option_price_and_pcode():
    products = by_pcode(extract_products(SAMPLE, BASE))
    assert products["1001"] == Product(
        pcode="1001",
        name="샘플전자 북프로 14 SB-1401",
        option="SSD 512GB",
        price=1_498_000,
        url="https://prod.danawa.com/info/?pcode=1001&cate=112758",
    )
    assert (products["1002"].option, products["1002"].price) == ("SSD 1TB", 1_517_810)
    assert products["1003"].price == 1_659_740


def test_option_rows_share_the_card_name():
    products = by_pcode(extract_products(SAMPLE, BASE))
    assert {products[p].name for p in ("1001", "1002", "1003")} == {"샘플전자 북프로 14 SB-1401"}


def test_card_without_option_label_has_no_option():
    products = by_pcode(extract_products(SAMPLE, BASE))
    assert products["2001"].option is None
    assert products["2001"].price == 2_798_800
    assert products["2001"].name == "예시컴퓨터 울트라 16"


def test_duplicate_pcodes_are_reported_once():
    pcodes = [p.pcode for p in extract_products(SAMPLE, BASE)]
    assert len(pcodes) == len(set(pcodes))


def test_excludes_ads_skeleton_cards_and_cards_without_price():
    pcodes = {p.pcode for p in extract_products(SAMPLE, BASE)}
    assert pcodes == {"1001", "1002", "1003", "2001"}  # 3001(가격 없음), 광고(pcode 없음), 스켈레톤 제외


def test_relative_hrefs_are_resolved_against_base_url():
    html = (
        '<div class="dnw-product-list-item">'
        '<a href="/info/?pcode=9" aria-label="상대경로 상품 상세보기"></a>'
        '<a href="/info/?pcode=9" aria-label="12,000원"></a></div>'
    )
    (product,) = extract_products(html, BASE)
    assert product.url == "https://prod.danawa.com/info/?pcode=9"


@pytest.mark.parametrize("html", ["", "<html></html>", "<p>상품 없음</p>", "<div class='dnw-product-list-item'></div>"])
def test_pages_without_products_return_empty_list(html):
    assert extract_products(html, BASE) == []


def test_large_prices_and_no_thousand_separator_labels():
    html = (
        '<div class="dnw-product-list-item"><a href="/info/?pcode=1" aria-label="고가 상품 상세보기"></a>'
        '<a href="/info/?pcode=1" aria-label="12,345,000원"></a>'
        '<a href="/info/?pcode=2" aria-label="쉼표 없는 가격 500원"></a></div>'
    )
    prices = {p.pcode: p.price for p in extract_products(html, BASE)}
    assert prices == {"1": 12_345_000}  # 쉼표 형식이 아닌 라벨은 가격으로 보지 않는다
