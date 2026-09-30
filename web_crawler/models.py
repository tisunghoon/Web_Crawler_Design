from dataclasses import dataclass, field


@dataclass
class DownloadResult:
    url: str
    status: str  # "ok" | "skipped" | "error" | "redirect"
    html: str | None = None
    redirect_url: str | None = None
    error_reason: str | None = None


@dataclass
class ParsedPage:
    url: str
    title: str
    body_text: str
    extracted_urls: list[str] = field(default_factory=list)


@dataclass
class DuplicateResult:
    verdict: str  # "new" | "duplicate" | "empty"
    md5_hash: str


@dataclass
class StoredPage:
    url: str
    title: str
    body_text: str
    extracted_urls: list[str]
    crawled_at: str  # UTC ISO 8601
    md5_hash: str


@dataclass
class CrawlSummary:
    total_pages: int
    skipped_urls: int
    duplicate_count: int
    elapsed_seconds: float
    save_failed: bool = False
