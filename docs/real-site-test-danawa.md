# 다나와 소규모 실사이트 테스트 결과

로컬 서버와 모킹으로만 검증했던 크롤러를 실제 사이트(다나와)에서 소규모로 돌려 본 기록입니다. 이슈 #39.

## 조건

- 대상: `www.danawa.com`(robots.txt, 홈페이지 분석), `shop.danawa.com`(조립PC), 링크로 따라간 `pc26.danawa.com`
- 안전 조건: 시작 전 robots.txt 확인, `--delay 2`, `--max-pages 8`, `--max-depth 1`, 한 번에 한 세션, 차단(403 등) 시 즉시 중단
- 총 요청: 17회(리다이렉트 제외). 홈페이지 2(분석용으로 한 번, 저장용으로 한 번), robots.txt 4(www 1, shop 2, pc26 1), 페이지 11(1차 3 + 2차 8). 실행마다 robots.txt 캐시를 새로 만들어 shop은 2번 요청했습니다. 홈페이지 2회와 robots.txt는 이 세션의 실행 기록 기준이며 크롤러 로그로는 페이지 요청만 셀 수 있습니다.
- 수집한 본문은 저장소에 커밋하지 않았습니다(저작권, 이용 약관). 아래에는 URL, 제목, 집계만 있습니다.

## 실행 결과

| 회차 | 크롤러 UA | 대상 | 결과 |
|------|-----------|------|------|
| 1차 | `python-requests` 기본값 | `shop.danawa.com` 시드 3개 | robots.txt 포함 전부 **403**, 수집 0, 건너뜀 3. 안전 조건에 따라 즉시 중단 |
| 2차 | `web-crawler-toy/0.1 (learning project)` | 같은 시드 3개, 깊이 1, 최대 8페이지 | **수집 8**, 건너뜀 725(723건은 깊이 초과), 중복 0, 10.6초 |

1차와 2차 사이에 의도적으로 바꾼 것은 User-Agent(PR #43)와 robots.txt 매칭(PR #41)입니다. 시각, 세션, IP는 통제하지 않았습니다. 식별 가능한 UA로 보낸 `www.danawa.com` 요청은 처음부터 200이었습니다(이 세션의 실행 출력 기준). UA가 403의 원인이었을 수 있지만, 각 조건에서 요청이 1회씩뿐이라 확정할 수 없습니다. 위장 UA나 차단 우회는 시도하지 않았습니다.

2차에 저장된 페이지 8개:

| 도메인 | 페이지 | 제목 |
|--------|--------|------|
| shop.danawa.com | `/shopmain/?logger_kw=dnw_gnb_pcmain` | 조립PC : 샵다나와 |
| shop.danawa.com | `/pcshop/?...representProductSeq=3109666` | 샵다나와 조립PC [인텔 i5-12400/내장VGA/16G] |
| shop.danawa.com | `/pcshop/?...representProductSeq=3154334` | 샵다나와 조립PC [AMD R5-5600/RTX5060 ...] |
| shop.danawa.com | `/main/` | 샵다나와 : 컴퓨터의 모든 것 |
| shop.danawa.com | `/ssancom/` | 싼컴 : 컴퓨터의 모든 것 |
| shop.danawa.com | `/shopmain/?...serviceGroupCode=46` | 기업용PC : 샵다나와 |
| pc26.danawa.com | `/bbs/` | PC26 : 컴퓨터의 모든 것 |
| pc26.danawa.com | `/bbs/?...boardSeq=194` | PC구매상담 : PC26 |

- 한글 인코딩은 정상입니다(깨짐 문자 0건). 조립PC 상품 페이지의 제목에 상품 구성(CPU/그래픽카드/메모리)이 들어 있습니다.
- robots.txt(`www.danawa.com`)는 `/my/`, `/member/`, `/user_report/`, `/error/`, `/404/`, `/elec/Management`, `?iframe=` 포함 URL만 금지합니다.

## 테스트로 발견해서 고친 결함

| 결함 | 원인 | 수정 |
|------|------|------|
| robots.txt 와일드카드(`Disallow: /*?iframe=*`)를 처리하지 못해 금지 URL을 허용으로 판정 | 표준 라이브러리 `RobotFileParser`가 `*`, `$`를 지원하지 않음 | 이슈 #40 / PR #41: RFC 9309 방식 매칭 직접 구현 |
| 크롤러가 신원을 밝히지 않음 | `requests` 기본 UA 사용 | 이슈 #42 / PR #43: `user_agent` 설정과 `--user-agent` 옵션 |

## 아직 남은 한계 (고치지 않음)

1. **컴퓨터/노트북 카테고리 목록에 도달하지 못했습니다.** 홈페이지의 카테고리 메뉴는 자바스크립트로 그려져서(`CategoryLnb().setListRootUrl(...)`) 정적 HTML에 메뉴 링크가 없습니다. `prod.danawa.com/list` 링크는 JS 문자열 안의 배너 1건뿐이었습니다. 이번에 수집된 것은 서버가 HTML로 내려주는 조립PC(`shop.danawa.com`) 페이지뿐입니다. 노트북 목록을 수집하려면 렌더링(브라우저 자동화)이나 사이트가 제공하는 다른 경로가 필요합니다.
2. **도메인 범위 제한이 없습니다.** 링크를 따라가다 `pc26.danawa.com` 같은 다른 서브도메인까지 수집했고, 깊이가 더 허용됐다면 `enuri.com` 같은 외부 사이트도 대상이 되었을 것입니다. 시드 도메인으로 제한하는 옵션이 필요합니다.
3. **최대 깊이에서 링크가 전부 "건너뜀"으로 집계됩니다.** 2차 실행의 건너뜀 725건 중 723건이 깊이 초과였고, 그만큼 WARNING 로그가 쏟아졌습니다. `.kiro/specs/web-crawler-toy/requirements.md`의 8.2와 10.5 문구대로 동작한 결과이지만, 요약 통계와 로그의 신호 대비 잡음이 나쁩니다. 최대 깊이 페이지에서는 링크를 아예 큐에 넣지 않는 방식이 낫습니다(요구사항 수정 필요).
4. **본문에 사이트 공통 메뉴와 다른 상품 정보가 섞입니다.** `<nav>`, `<footer>` 태그만 제거하므로 `div`로 만든 메뉴, 실시간 견적 목록, 다른 상품의 가격이 `body_text`에 그대로 들어옵니다. 상품 페이지 2개에서 콤마 숫자로 된 가격 표기가 각각 394건, 427건 잡혔지만 상당수는 그 상품의 가격이 아닙니다. 상품명, 가격, 사양을 구조화해서 얻으려면 사이트별 추출기가 필요합니다.
5. **robots.txt가 403이어도 "전부 허용"으로 처리합니다**(요구사항 4.4의 "실패하면 전체 허용"). 1차 실행에서 robots.txt와 모든 페이지가 403이었던 것처럼, 이는 허용이 아니라 차단 신호일 수 있습니다.

## 재현

```bash
.venv/bin/python -m web_crawler \
  "https://shop.danawa.com/shopmain/?logger_kw=dnw_gnb_pcmain" \
  --max-depth 1 --max-pages 8 --delay 2 --output result.jsonl -v
```

실제 사이트를 대상으로 할 때는 대상의 이용 약관과 robots.txt를 먼저 확인하고, 작은 값으로 시작하세요. 403, 429 같은 응답이 나오면 멈추고 재시도하거나 우회하지 마세요.
