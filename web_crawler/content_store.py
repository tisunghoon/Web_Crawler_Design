import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import islice

from web_crawler.models import StoredPage

logger = logging.getLogger(__name__)

MAX_FILE_RECORDS = 10_000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ContentStore:
    """URL을 키로 페이지를 저장한다. 같은 URL은 마지막에 저장한 값이 남는다."""

    def __init__(self) -> None:
        self._pages: dict[str, StoredPage] = {}

    def save(self, page: StoredPage) -> None:
        self._pages[page.url] = page

    def get(self, url: str) -> StoredPage | None:
        return self._pages.get(url)

    def all_urls(self) -> list[str]:
        return list(self._pages)

    def count(self) -> int:
        return len(self._pages)

    def flush_to_file(self, path: str) -> bool:
        """JSON Lines로 최대 10,000개 레코드를 저장한다. 실패하면 로그를 남기고 False."""
        try:
            with open(path, "w", encoding="utf-8") as f:
                for page in islice(self._pages.values(), MAX_FILE_RECORDS):
                    f.write(json.dumps(asdict(page), ensure_ascii=False) + "\n")
        except (OSError, UnicodeError) as e:
            logger.error("파일 저장 실패 (%s): %s", path, e)
            return False
        return True
