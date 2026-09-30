import argparse
import logging
import sys

from web_crawler.config import CrawlerConfig
from web_crawler.crawler import Crawler
from web_crawler.extractors import EXTRACTORS


def build_parser() -> argparse.ArgumentParser:
    defaults = CrawlerConfig()
    parser = argparse.ArgumentParser(prog="python -m web_crawler", description="BFS 웹 크롤러 토이 프로젝트")
    parser.add_argument("seeds", nargs="+", metavar="SEED_URL", help="크롤링을 시작할 URL (http:// 또는 https://)")
    parser.add_argument("--max-depth", type=int, default=defaults.max_depth, help="최대 크롤링 깊이 1~10 (기본 %(default)s)")
    parser.add_argument("--max-pages", type=int, default=defaults.max_pages, help="최대 수집 페이지 수 1~100000 (기본 %(default)s)")
    parser.add_argument("--delay", type=float, default=defaults.politeness_delay, help="같은 호스트 요청 간 최소 간격(초) 0~60 (기본 %(default)s)")
    parser.add_argument("--output", metavar="PATH", help="수집 결과를 저장할 JSON Lines 파일 경로")
    parser.add_argument("--user-agent", default=defaults.user_agent, help="요청에 실을 User-Agent. 크롤러임을 밝히는 값을 쓰세요 (기본 %(default)r)")
    parser.add_argument("--allow-domain", action="append", default=[], metavar="DOMAIN", help="시드 호스트 외에 허용할 도메인(하위 도메인 포함). 여러 번 지정 가능")
    parser.add_argument("--allow-any-domain", action="store_true", help="범위 제한을 끄고 모든 호스트를 따라감 (주의)")
    parser.add_argument("--extract", choices=sorted(EXTRACTORS), help="페이지에서 상품 정보를 구조화해 뽑을 사이트별 추출기")
    parser.add_argument("-v", "--verbose", action="store_true", help="INFO 로그 출력")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    options = {"save_to_file": True, "output_path": args.output} if args.output else {}
    config = CrawlerConfig(
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        politeness_delay=args.delay,
        user_agent=args.user_agent,
        allowed_domains=tuple(args.allow_domain),
        allow_any_domain=args.allow_any_domain,
        extractor=args.extract,
        **options,
    )
    try:
        crawler = Crawler.initialize(args.seeds, config)
    except ValueError as e:
        print(f"오류: {e}", file=sys.stderr)
        return 2
    summary = crawler.run()
    return 1 if summary.save_failed else 0


if __name__ == "__main__":
    sys.exit(main())
