import re
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from web_crawler.models import Product

CARD_CLASS = "dnw-product-list-item"
_DETAIL_SUFFIX = " 상세보기"
# 옵션 행의 aria-label. 예: "SSD 1TB 1,517,810원". 앞부분은 옵션명이고 없을 수도 있다.
_PRICE_LABEL = re.compile(r"^(?P<option>.*?)\s*(?P<price>\d{1,3}(?:,\d{3})+)\s*원$")


def extract_products(html: str, base_url: str) -> list[Product]:
    """다나와 상품 목록 페이지에서 상품을 뽑는다. 옵션마다 pcode가 달라 옵션 행 하나가 상품 하나다.

    Tailwind 유틸리티 클래스가 아니라 의미 있는 카드 클래스와 접근성 속성(aria-label)에 기대서,
    스타일 변경에는 덜 민감하다. 광고 링크(pcode 없음)와 이름이나 가격이 없는 카드는 제외한다.
    """
    products: dict[str, Product] = {}
    for card in BeautifulSoup(html, "html.parser").select(f".{CARD_CLASS}"):
        name = _card_name(card)
        if not name:
            continue
        for anchor in card.find_all("a", href=True):
            product = _option_product(anchor, name, base_url)
            if product:
                products.setdefault(product.pcode, product)
    return list(products.values())


def _card_name(card: Tag) -> str | None:
    for anchor in card.find_all("a", attrs={"aria-label": True}):
        label = anchor["aria-label"].strip()
        if label.endswith(_DETAIL_SUFFIX):
            return label.removesuffix(_DETAIL_SUFFIX).strip() or None
    return None


def _option_product(anchor: Tag, name: str, base_url: str) -> Product | None:
    match = _PRICE_LABEL.match(anchor.get("aria-label", "").strip())
    if not match:
        return None
    url = urljoin(base_url, anchor["href"])
    pcode = parse_qs(urlparse(url).query).get("pcode", [None])[0]
    if not pcode:  # 광고 브리지 링크 등
        return None
    return Product(
        pcode=pcode,
        name=name,
        option=match["option"].strip() or None,
        price=int(match["price"].replace(",", "")),
        url=_canonical_url(url, pcode),
    )


def _canonical_url(url: str, pcode: str) -> str:
    """추적용 파라미터(adinflow 등)를 빼고 pcode와 카테고리만 남긴다."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    kept = [f"pcode={pcode}"] + ([f"cate={query['cate'][0]}"] if "cate" in query else [])
    return parsed._replace(query="&".join(kept), fragment="").geturl()
