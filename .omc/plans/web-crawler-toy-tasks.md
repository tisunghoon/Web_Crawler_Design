# web-crawler-toy 작업 계획

- 상태: **pending approval** (구현 착수 전 승인 필요)
- 입력 문서: `.kiro/specs/web-crawler-toy/requirements.md` (요구사항 1~11), `design.md` (컴포넌트·속성 11개)
- 참고: `.kiro/specs/web-crawler-toy/tasks.md`는 현재 빈 파일. 승인 후 이 계획을 체크리스트로 옮길 수 있음.
- 스택: Python 3.10+, requests, BeautifulSoup4, pytest, hypothesis, responses, pytest-httpserver

## 0. 구현 전 확정해야 할 결정 (문서 간 충돌/공백)

| # | 충돌·공백 | 근거 | 권장안 |
|---|-----------|------|--------|
| D1 | 우선순위 타입: 요구사항 2.1은 "정수", 1.2·design은 float(1.0) | req 1.2 / 2.1, design `push(priority: float)` | float로 통일, 요구사항 2.1 문구 수정 |
| D2 | 레벨 단위 BFS(req 10.2)와 우선순위 힙이 충돌. 시드 외 URL의 priority 산정식이 없어 우선순위 순으로 꺼내면 깊이 순서가 깨질 수 있음 | req 10.2 vs 2.4 | `priority = 1.0 / (1 + depth)`, 동점은 삽입 순번(FIFO) tie-break |
| D3 | robots `Crawl-delay`(req 4.5)는 호스트별 Politeness_Delay를 덮어써야 하는데, Frontier와 RobotsTxtCache 사이 연결 경로가 design에 없음 | req 4.5, design 의존 그래프 | `URLFrontier.set_host_delay(host, seconds)` 추가. Crawler가 robots 조회 후 호출 |
| D4 | DNS_Resolver 호출 주체가 흐름도(Crawler)와 의존 그래프(Downloader)에서 다름. `requests`는 얻은 IP를 쓰지 않음 | design 흐름도 vs 의존 그래프 | Crawler가 다운로드 전에 호출하는 게이트(캐시 워밍·실패 스킵)로 통일. Downloader→DNS 의존 제거 |
| D5 | DuplicateDetector가 "Content_Store의 해시"를 조회한다고 하나(req 7.2), design은 자체 dict 보유 | req 7.2 vs design DuplicateDetector | 자체 dict 유지(design 따름). 요구사항 문구는 용어 정정 |
| D6 | design 테스팅 표는 속성 12개, 본문 속성 목록은 11개, 번호 매핑도 다름 | design 정확성 속성 vs 속성 테스트 표 | 본문 속성 1~11을 기준으로 표 재작성 |
| D7 | 리다이렉트 URL의 depth와 원본 URL의 visited 처리가 미정 | req 5.3, 9.2 | 리다이렉트 대상은 원본과 같은 depth. 원본은 visited에 기록 |
| D8 | Politeness 대기가 `time.sleep`이면 테스트가 느리고 불안정 | req 2.5, 2.6 | Frontier·Downloader에 `clock`/`sleep` 주입 (기본값은 실제 `time`) |

> D1~D3는 구현 방식을 바꾸므로 착수 전 결정 필요. D4~D8은 권장안으로 진행 가능.

## 1. 작업 목록

표기: `[P]` = 선행 작업이 끝난 뒤 병렬 가능 / `PBT n` = design 속성 번호 / `Req` = 요구사항 번호

### Phase 0. 기반 (직렬)

**T0. 프로젝트 골격**
- `pyproject.toml`(또는 requirements.txt), `web_crawler/`·`tests/` 패키지, pytest·hypothesis 설정(`max_examples=100`), `.gitignore`
- 산출: 빈 패키지에서 `pytest` 실행이 성공
- 완료 기준: `pytest -q`가 0 tests 또는 스모크 테스트 1개로 통과

**T0b. GitHub 이슈·PR 템플릿** (T0과 병행 가능, 이후 모든 작업의 선행)
- 원본: `EduLens/Jjikovoca`의 `.github/` (Jjikovoca, -web, -server 3곳이 바이트 단위로 동일함을 확인)
- 생성 위치: `.github/PULL_REQUEST_TEMPLATE.md`, `.github/ISSUE_TEMPLATE/` 아래 5종 (원본 파일명·이모지·섹션 구조 그대로)
  - 🚀-기능-구현.md (`[FEAT]`, enhancement), 🐞-버그해결.md (`[BUG]`, bug), 🧹-리팩토링.md (`[REFACTOR]`, refactor), 📑-문서화.md (`[DOCS]`, documentation), 🧭-환경설정.md (`[CONFIG]`, config)
- 이 저장소에 맞춰 바꾸는 부분은 Java/Node 전용 문구 2곳뿐:
  - 버그 템플릿 환경 정보 `JDK / Node 버전: [예: Java 17, Node 20]` → `Python 버전: [예: Python 3.11]`
  - 문서화 템플릿 예시 `UserService.java 주석` → `frontier.py docstring`
- 새 라벨(enhancement, bug, refactor, documentation, config)이 원격에 없으면 이슈 생성 시 실패하므로 T0b에서 `gh label list`로 확인 후 부족분 생성 (외부 행위, 사전 확인)
- 완료 기준: 원본과 diff했을 때 위 2곳 외 차이 없음. 5종 템플릿이 GitHub 이슈 생성 화면에 노출됨

**T1. 공통 모델·설정** (T0 이후)
- `models.py`: `DownloadResult`, `ParsedPage`, `DuplicateResult`, `StoredPage`, `CrawlSummary`
- `config.py`: `CrawlerConfig`(frozen) + 범위 검증 함수 (depth 1~10, pages 1~100,000, delay 0~60)
- Req 1.4, 1.5, 1.8
- 완료 기준: 기본값이 depth 3 / pages 1000 / delay 1.0. 경계값 0, 1, 10, 11에서 각각 기대대로 통과·`ValueError`

### Phase 1. 독립 컴포넌트 (전부 [P], T1 이후)

| 작업 | 파일 | 핵심 내용 | Req | PBT | 완료 기준 |
|------|------|-----------|-----|-----|-----------|
| **T2 VisitedURLStore** | `visited_store.py`, `test_visited_store.py` | `set` 기반 `add/contains/count` | 9.1, 9.4~9.6 | 8 | 같은 URL 반복 `add` 후 `count`가 고유 URL 수와 같음 |
| **T3 ContentStore** | `content_store.py`, `test_content_store.py` | dict 저장, `crawled_at` UTC ISO 8601, `all_urls`, `flush_to_file`(JSONL, 최대 10,000줄), 저장 실패 시 로그+실패 플래그 | 11.1~11.6 | 9, 10 | 저장→조회 라운드트립 동등, 덮어쓰기 시 최신값, 없는 URL은 `None`, 쓰기 불가 경로에서 예외 대신 실패 반영 |
| **T4 DuplicateDetector** | `duplicate.py`, `test_duplicate.py` | 태그·앞뒤 공백 제거 후 MD5, verdict `new/duplicate/empty`, URL·해시·판정 로그 | 7.1~7.5 | 5 | 동일 본문 두 URL은 두 번째가 `duplicate`이고 해시 동일. 빈 본문은 `empty`이며 저장 허용 |
| **T5 URLFilter** | `url_filter.py`, `test_url_filter.py` | 검사 순서: 스킴→길이 2,048→깊이→경로 3회 반복(대소문자 무시)→방문 여부. 첫 위반 사유만 로그 | 8.1~8.7 | 6, 7 | 규칙별 거부 케이스 5개 + 복수 위반 시 첫 사유만 기록. 거부면 사유 문자열, 허용이면 `None` |
| **T6 ContentParser** | `parser.py`, `test_parser.py` | title 추출(없으면 `""`), script/style/nav/footer 제거 후 공백 결합, href 규칙, `urljoin`, 예외 시 빈 `ParsedPage` | 6.1~6.8 | 4 | `extracted_urls`가 전부 절대 http(s), `javascript:`·`mailto:`·`#` 미포함. base_url 없는 상대경로 제외. 깨진 HTML에서 예외 없이 빈 결과 |
| **T7 DNSResolver** | `dns_resolver.py`, `test_dns_resolver.py` | TTL 600s 캐시, 만료 시 제거 후 재조회, 실패 시 `None`. `socket.getaddrinfo`는 주입/모킹 | 3.1~3.5 | 3 | 히트 시 조회 0회, TTL 만료 시 재조회 1회, NXDOMAIN·타임아웃에서 `None` |
| **T8 URLFrontier** | `frontier.py`, `test_frontier.py` | 힙 Front Queue(D2 tie-break), 호스트별 `deque` Back Queue, 마지막 요청 시각, 완전 일치 중복 거부, `set_host_delay`(D3), 주입 가능한 clock/sleep(D8) | 2.1~2.7, 1.2 | 1, 2 | 같은 URL 재삽입은 `False`. `pop` 순서가 우선순위 내림차순. 첫 요청은 즉시, 이후는 delay 경과 후에만 반환. 호스트별 delay 오버라이드 동작 |

- T8이 가장 복잡하므로 가장 먼저 착수 권장.
- T8은 Back Queue가 pop 시점에 대기 상태일 때 다른 호스트 URL을 먼저 반환할지 정해야 함. 요구사항 2.6은 "최대 delay만큼 대기"이므로 단순 대기로 시작하고, 개선은 후속 과제로 둔다.

### Phase 2. 네트워크 계층 (T1·T7·T8 이후, 병렬 가능)

**T9. RobotsTxtCache** `robots_cache.py`, `test_robots_cache.py`
- `RobotFileParser` 활용, 도메인별 캐시, 첫 접근 시 `{scheme}://{domain}/robots.txt` 요청, 실패·404면 빈 규칙(전체 허용), `Disallow` prefix 매칭, `Crawl-delay` 최대 300초로 제한
- Req 4.1~4.5
- 완료 기준(`responses` 모킹): 같은 도메인 2회 조회 시 HTTP 1회, Disallow 경로 차단, 404·연결 실패 시 전체 허용, Crawl-delay 999 → 300

**T10. Downloader** `downloader.py`, `test_downloader.py` (T9 이후)
- 30초 타임아웃, 200 → html, 301/302 → `redirect`(최대 5회), 4xx → visited 기록 후 skip, 5xx·타임아웃 → 5초 간격 최대 2회 재시도 후 실패, `text/html`이 아니거나 Content-Type 없음 → skip, robots Disallow → skip
- Req 5.1~5.7, 9.2, 9.3, 4.3 / D4, D7, D8
- 완료 기준: 상태코드 200/301/302/404/500/타임아웃별 결과 검증, 재시도 정확히 2회(총 3번 요청), sleep 주입으로 테스트 시간 1초 미만

### Phase 3. 오케스트레이션 (모든 컴포넌트 이후, 직렬)

**T11. Crawler** `crawler.py`, `test_crawler.py`
- `initialize`: 빈 seed → `ValueError`, 잘못된 설정 → `ValueError`, 스킴 없는 seed 제외+로그, seed 중복 제거, priority 1.0으로 삽입
- `run`: pop → filter → DNS → robots(→`set_host_delay`) → download → parse → duplicate → store(→visited) → 추출 URL에 depth+1 부여·필터·push. `max_pages` 도달 시 즉시 종료, frontier 비면 정상 종료, 깊이 N 완료 후 N+1 처리
- `CrawlSummary`: 저장 페이지 수, (필터+다운로더) skip 합산, 중복 수, 경과 초 → 표준 출력. 파일 저장 옵션 시 `flush_to_file`, 실패는 요약에 반영
- Req 1.1~1.8, 10.1~10.6, 11.5, 11.6 / PBT 11
- 완료 기준: 아래 T12 통합 시나리오 통과 + `max_pages`가 중복 페이지를 세지 않음(Content_Store 저장 수 기준, req 10.3)

### Phase 4. 통합·마무리

**T12. 통합 테스트** `tests/test_integration.py` (`pytest-httpserver`)
- 3~5개 페이지 사이트: 링크 체인, 중복 본문 1쌍, robots Disallow 1경로, 404 링크 1개, 리다이렉트 1개
- 검증: ContentStore 내용, `CrawlSummary` 각 수치, BFS 방문 순서(깊이 오름차순)
- 완료 기준: 위 시나리오의 기대값이 정확히 일치

**T13. 진입점·문서** `web_crawler/__main__.py`(argparse: seed, `--max-depth`, `--max-pages`, `--delay`, `--output`), README에 실행법·구조·학습 포인트(BFS vs DFS, Frontier 2단 큐)
- 완료 기준: `python -m web_crawler <seed>`가 로컬 테스트 서버에서 요약 통계를 출력

**T14. 최종 검증** (별도 검증 레인)
- 전체 `pytest` 통과, PBT 11개 모두 `max_examples>=100`, 각 요구사항의 인수 기준이 최소 1개 테스트에 대응되는지 추적표 확인
- 빈 테스트·`skip`·TODO 잔존 여부 점검

## 1.5 작업별 공통 절차 (T1~T13 모두 적용)

각 작업은 `github-issue-pr-workflow` 흐름으로 진행하고, PR 전에 `ai-slop-cleaner` 패스를 넣는다.

| 순서 | 단계 | 내용 |
|------|------|------|
| 1 | 이슈 | 작업 1개 = 이슈 1개. 템플릿 매핑: T0·T0b는 CONFIG, T1~T11은 FEAT, T12는 FEAT(테스트), T13은 DOCS, 버그 발견 시 BUG, 구조 개선은 REFACTOR. 본문에 Req 번호와 완료 기준 인용 |
| 2 | 브랜치 | `gh issue develop --checkout`으로 이슈에 연결된 브랜치 생성. 레인별 병렬 작업은 각자 워크트리·자기 파일만 수정 |
| 3 | 구현 | 논리 단위 커밋(~300~400줄), 착수 전 계획 승인 게이트, 테스트와 함께 작성 |
| 4 | **ai-slop-cleaner** | 해당 작업의 변경 파일에 한정해 실행. 불필요한 주석·과한 방어 코드·중복 제거 등. 동작 보존을 위해 정리 전 테스트를 먼저 통과시키고, 정리 후 다시 통과시킴. 작성 패스와 정리·검토 패스는 분리(같은 컨텍스트에서 자체 승인 금지) |
| 5 | 테스트 | 변경분 테스트를 포함한 전체 `pytest` 통과가 push 게이트 |
| 6 | PR | push 후 `.github/PULL_REQUEST_TEMPLATE.md`로 PR 생성. `Closes #이슈번호`, 작업 의도·근거(Why) 서술, 셀프 체크리스트 채움 |

- 이슈 생성, 브랜치 push, PR 생성은 외부에 보이는 행위이므로 실행 직전에 사용자 확인을 받는다. push는 staged-commit 규칙에 따라 사용자가 직접 하는 것이 기본.
- 브랜치 파기·정리 전에는 main 최신화 여부 확인.
- T14 최종 검증은 이슈·PR 링크가 각 작업에 연결됐는지도 점검.

## 2. 의존 관계와 병렬 레인 (`/team` 실행 시)

```
T0 → T1 ─┬→ T2 ┐
         ├→ T3 │
         ├→ T4 ├──────────────┐
         ├→ T5 │              │
         ├→ T6 ┘              │
         ├→ T7 ──┐            ├→ T11 → T12 → T13 → T14
         └→ T8 ──┼→ T9 → T10 ─┘
                 └(set_host_delay)
```

| 레인 | 담당 작업 | 비고 |
|------|-----------|------|
| A | T8 → (T9) → T10 | 가장 긴 경로. 먼저 시작 |
| B | T7, T5, T2 | 짧은 작업 묶음 |
| C | T6, T4, T3 | 짧은 작업 묶음 |
| 직렬 | T0, T1, T11~T14 | 병합 지점 |

레인끼리 같은 파일을 건드리지 않음 (T1이 `models.py`를 확정하므로 이후엔 읽기 전용).

## 3. 위험과 대응

| 위험 | 대응 |
|------|------|
| D2 미결정 시 BFS 깊이 순서 검증(req 10.2)이 우연히 통과/실패 | T8에서 priority 산정식을 먼저 확정하고 T12에서 깊이 순서를 명시 검증 |
| 시간 의존 코드(TTL, politeness, 재시도 5초)로 테스트가 느리거나 flaky | 전 컴포넌트 clock/sleep 주입, 실제 sleep 금지 |
| Hypothesis가 `st.urls()` 등에서 예외적 URL을 만들어 속성 테스트가 불안정 | 전략을 좁게 정의하고 실패 시 `@example`로 고정 |
| PBT 번호가 design 표와 어긋나 추적 실패 | D6 정리 후 주석 태그 `# Feature: web-crawler-toy, Property {n}` 통일 |
| 외부 네트워크 사용으로 테스트 불안정 | 단위는 `responses`, 통합은 로컬 `pytest-httpserver`만 사용, 실제 DNS는 모킹 |

## 4. 승인 후 실행 방식 (택1)

- `/team`: 위 레인 A/B/C 병렬 + 검증 레인 분리 (권장: 컴포넌트가 독립적이라 병렬 이득이 큼)
- `ralph`: 단일 레인 직렬 실행 + 각 작업 검증

## 5. 변경 이력

- v1: 초안 (direct 모드, Analyst·Critic 검토 미실시)
- v1.2: T0b(이슈·PR 템플릿, Jjikovoca 원본 기반) 추가, §1.5 작업별 공통 절차(github-issue-pr-workflow + ai-slop-cleaner) 추가.
- v1.1: D1~D3 권장안 확정. requirements 2.1 수정 및 2.8·2.9 추가, design URLFrontier에 `set_host_delay`와 priority 산식 반영. 실행 방식은 team 병렬 선호로 기록(실행 승인은 아직 아님).
