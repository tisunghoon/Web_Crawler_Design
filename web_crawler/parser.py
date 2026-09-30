import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from web_crawler.models import ParsedPage

logger = logging.getLogger(__name__)

_NOISE_TAGS = ("script", "style", "nav", "footer")
_ABSOLUTE_PREFIXES = ("http://", "https://")
_RELATIVE_PREFIXES = ("/", "./", "../")


class ContentParser:
    def parse(self, html: str, base_url: str | None = None) -> ParsedPage:
        url = base_url or ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text().strip() if soup.title else ""
            extracted_urls = self._extract_urls(soup, base_url)
            for tag in soup(_NOISE_TAGS):
                tag.decompose()
            body_text = " ".join(soup.stripped_strings)
        except Exception:
            logger.exception("HTML 파싱 실패 url=%s", url)
            return ParsedPage(url=url, title="", body_text="", extracted_urls=[])
        return ParsedPage(url=url, title=title, body_text=body_text, extracted_urls=extracted_urls)

    @staticmethod
    def _extract_urls(soup: BeautifulSoup, base_url: str | None) -> list[str]:
        urls = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.lower().startswith(_ABSOLUTE_PREFIXES):
                urls.append(href)
            elif href.startswith(_RELATIVE_PREFIXES) and base_url:
                absolute = urljoin(base_url, href)
                if absolute.lower().startswith(_ABSOLUTE_PREFIXES):
                    urls.append(absolute)
        return urls
