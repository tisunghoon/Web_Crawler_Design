from dataclasses import dataclass

DEFAULT_USER_AGENT = "web-crawler-toy/0.1 (learning project)"


@dataclass(frozen=True)
class CrawlerConfig:
    max_depth: int = 3
    max_pages: int = 1000
    politeness_delay: float = 1.0
    save_to_file: bool = False
    output_path: str = "crawl_output.jsonl"
    user_agent: str = DEFAULT_USER_AGENT
    allowed_domains: tuple[str, ...] = ()
    allow_any_domain: bool = False

    def validate(self) -> None:
        if not 1 <= self.max_depth <= 10:
            raise ValueError(f"max_depth는 1~10이어야 합니다: {self.max_depth}")
        if not 1 <= self.max_pages <= 100_000:
            raise ValueError(f"max_pages는 1~100,000이어야 합니다: {self.max_pages}")
        if not 0 <= self.politeness_delay <= 60:
            raise ValueError(f"politeness_delay는 0~60초여야 합니다: {self.politeness_delay}")
        if not self.user_agent.strip():
            raise ValueError("user_agent는 비어 있을 수 없습니다.")
        for domain in self.allowed_domains:
            if not domain.strip() or any(ch in domain for ch in "/:"):
                raise ValueError(f"allowed_domains에는 도메인 이름만 쓸 수 있습니다: {domain!r}")
