from collections.abc import Callable

from web_crawler.extractors.danawa import extract_products as extract_danawa_products
from web_crawler.models import Product

# 이름으로 고르는 사이트별 상품 추출기. 함수는 (html, 페이지 URL)을 받아 상품 목록을 돌려준다.
EXTRACTORS: dict[str, Callable[[str, str], list[Product]]] = {
    "danawa": extract_danawa_products,
}
