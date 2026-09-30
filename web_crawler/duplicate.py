import hashlib
import logging
import re

from web_crawler.models import DuplicateResult

logger = logging.getLogger(__name__)

_TAG = re.compile(r"<[^>]*>")


def normalize(text: str) -> str:
    return _TAG.sub("", text).strip()


class DuplicateDetector:
    """정규화한 본문의 MD5로 중복 페이지를 판정한다."""

    def __init__(self) -> None:
        self._first_url_by_hash: dict[str, str] = {}

    def check_and_register(self, url: str, body_text: str) -> DuplicateResult:
        text = normalize(body_text)
        md5_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

        if not text:
            verdict = "empty"
        elif md5_hash in self._first_url_by_hash:
            verdict = "duplicate"
        else:
            verdict = "new"
            self._first_url_by_hash[md5_hash] = url

        logger.info("중복 판정 url=%s md5=%s verdict=%s", url, md5_hash, verdict)
        return DuplicateResult(verdict=verdict, md5_hash=md5_hash)
