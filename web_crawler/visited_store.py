class VisitedURLStore:
    """방문한 URL을 set(해시 테이블)에 저장해 O(1)로 조회한다."""

    def __init__(self) -> None:
        self._urls: set[str] = set()

    def add(self, url: str) -> None:
        self._urls.add(url)

    def contains(self, url: str) -> bool:
        return url in self._urls

    def count(self) -> int:
        return len(self._urls)
