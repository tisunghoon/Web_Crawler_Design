# Requirements Document

## Introduction

웹 크롤러 토이 프로젝트는 웹 크롤러 시스템 설계의 핵심 개념을 학습 목적으로 직접 구현해보는 프로젝트입니다.
BFS 기반 탐색, URL Frontier(우선순위 큐 + 예의 큐), robots.txt 준수, 중복 콘텐츠 감지, DNS 캐싱 등
실제 대규모 웹 크롤러의 핵심 컴포넌트를 토이 규모로 축소하여 코드로 확인할 수 있도록 구성합니다.

**대상 규모 (토이):**
- 동시 크롤링 대상: 최대 1,000개 도메인
- 단일 크롤링 세션당 최대 10,000 페이지
- 크롤링 깊이: 최대 5단계

---

## Glossary

- **Crawler**: 시드 URL에서 출발하여 웹 페이지를 수집하는 시스템 전체
- **URL_Frontier**: 크롤링 대기 중인 URL을 관리하는 저장소. 전면 큐(우선순위)와 후면 큐(예의)로 구성
- **Front_Queue**: URL_Frontier의 전면 큐. 우선순위에 따라 URL을 정렬하여 관리
- **Back_Queue**: URL_Frontier의 후면 큐. 동일 호스트에 대한 요청 간격을 제어하는 예의(Politeness) 큐
- **Downloader**: robots.txt 규칙을 확인한 후 대상 URL의 HTML을 HTTP로 다운로드하는 컴포넌트
- **DNS_Resolver**: 도메인 이름을 IP 주소로 변환하고 결과를 캐싱하는 컴포넌트
- **Content_Parser**: 다운로드된 HTML에서 텍스트와 링크를 추출하는 컴포넌트
- **Duplicate_Detector**: MD5 해시를 이용해 이미 수집한 콘텐츠와의 중복 여부를 판별하는 컴포넌트
- **URL_Filter**: 수집 범위, 깊이, URL 길이 등의 규칙에 따라 URL의 크롤링 허용 여부를 판단하는 컴포넌트
- **Visited_URL_Store**: 방문한 URL을 저장하고 중복 방문을 방지하는 저장소 (해시 테이블 기반)
- **Content_Store**: 파싱된 페이지 데이터(URL, 제목, 본문, 링크 목록)를 저장하는 저장소
- **Robots_txt_Cache**: 도메인별 robots.txt 내용을 캐싱하여 반복 요청을 방지하는 저장소
- **Seed_URL**: 크롤링의 시작점이 되는 초기 URL 목록
- **Crawl_Depth**: 시드 URL로부터의 링크 추적 횟수. 0은 시드 URL 자체를 의미
- **Politeness_Delay**: 동일 호스트에 대한 연속 요청 사이의 최소 대기 시간

---

## Requirements

### 요구사항 1: 크롤러 초기화 및 시드 URL 처리

**사용자 스토리:** 학습자로서, 시드 URL 목록을 입력하여 크롤러를 시작하고 싶다. 그래야 원하는 사이트부터 크롤링을 시작할 수 있다.

#### 인수 기준

1. WHEN Crawler가 시작될 때, THE Crawler SHALL 하나 이상의 Seed_URL 목록을 입력으로 받아 크롤링 세션을 초기화한다.
2. WHEN Crawler가 초기화될 때, THE URL_Frontier SHALL 모든 Seed_URL을 초기 우선순위 값(1.0)과 함께 Front_Queue에 삽입한다.
3. WHEN Seed_URL 목록이 비어 있을 때, THE Crawler SHALL 오류 메시지를 반환하고 크롤링 세션을 시작하지 않는다.
4. WHEN Crawler가 시작될 때, THE Crawler SHALL 최대 크롤링 깊이(Crawl_Depth, 1~10), 최대 페이지 수(1~100,000), Politeness_Delay(0~60초)를 설정값으로 받는다.
5. WHEN 설정값이 제공되지 않을 때, THE Crawler SHALL 기본값(최대 깊이 3, 최대 페이지 수 1,000, Politeness_Delay 1초)을 사용한다.
6. WHEN Seed_URL 목록에 `http://` 또는 `https://` 스킴이 없는 URL이 포함될 때, THE Crawler SHALL 해당 URL을 무효 URL로 처리하고 오류를 기록한 후 나머지 유효한 URL로 초기화를 진행한다.
7. WHEN Seed_URL 목록에 중복된 URL이 포함될 때, THE Crawler SHALL 중복을 제거하고 고유한 URL만으로 URL_Frontier를 초기화한다.
8. WHEN 설정값이 허용 범위를 벗어날 때, THE Crawler SHALL 오류를 반환하고 크롤링 세션을 시작하지 않는다.

---

### 요구사항 2: URL Frontier 관리 (전면 큐 + 후면 큐)

**사용자 스토리:** 학습자로서, URL Frontier가 우선순위 큐와 예의 큐로 구성되는 원리를 코드로 확인하고 싶다. 그래야 실제 크롤러의 URL 스케줄링 방식을 이해할 수 있다.

#### 인수 기준

1. THE Front_Queue SHALL 우선순위 점수(실수)를 기준으로 URL을 내림차순 정렬하여 저장하며, 점수가 같은 URL은 삽입된 순서(FIFO)대로 제공한다.
2. WHEN URL이 Front_Queue에 삽입될 때, THE Front_Queue SHALL 해당 URL의 우선순위 점수를 함께 기록한다.
3. THE Back_Queue SHALL 동일한 호스트(도메인)를 가진 URL들을 동일한 큐 버킷에 그룹화하여 관리한다.
4. WHEN Downloader가 다음 URL을 요청할 때, THE URL_Frontier SHALL Front_Queue에서 가장 높은 우선순위의 URL을 선택한 후 해당 호스트의 Back_Queue 버킷으로 라우팅하여 제공하며, 해당 호스트의 Back_Queue 버킷이 없을 때는 새 버킷을 생성한다.
5. WHEN Back_Queue에서 URL이 선택될 때, THE Back_Queue SHALL 해당 호스트에 대한 첫 번째 요청이거나 마지막 요청 시각으로부터 Politeness_Delay 이상 경과한 경우에만 URL을 즉시 반환한다.
6. WHILE Politeness_Delay가 경과하지 않은 경우, THE Back_Queue SHALL 해당 호스트의 URL 반환을 최대 Politeness_Delay 시간만큼 대기한다.
7. THE URL_Frontier SHALL 동일한 URL이 중복으로 삽입되는 경우 문자열 완전 일치 기준으로 판별하여 삽입을 거부한다.
8. WHEN Crawler가 Seed_URL이 아닌 추출된 URL을 URL_Frontier에 삽입할 때, THE Crawler SHALL 우선순위 점수를 `1.0 / (1 + Crawl_Depth)`로 부여하여 얕은 깊이의 URL이 먼저 제공되도록 한다.
9. WHEN 특정 호스트에 대한 Politeness_Delay가 개별 지정될 때, THE Back_Queue SHALL 해당 호스트에 대해 설정된 기본 Politeness_Delay 대신 지정된 값을 사용한다.

---

### 요구사항 3: DNS 해석 및 캐싱

**사용자 스토리:** 학습자로서, DNS 캐싱이 크롤러 성능에 미치는 영향을 확인하고 싶다. 그래야 DNS 조회 비용 최적화 원리를 이해할 수 있다.

#### 인수 기준

1. WHEN Downloader가 URL의 호스트에 대한 IP 주소를 요청할 때, IF DNS_Resolver의 캐시에 해당 호스트의 레코드가 존재하고 TTL이 만료되지 않은 경우, THEN THE DNS_Resolver SHALL 캐시된 IP 주소를 즉시 Downloader에 반환한다.
2. WHEN Downloader가 URL의 호스트에 대한 IP 주소를 요청할 때, IF DNS_Resolver의 캐시에 해당 호스트의 레코드가 존재하지 않는 경우, THEN THE DNS_Resolver SHALL 시스템 DNS 조회를 수행하고 결과를 캐시에 저장한 후 IP 주소를 Downloader에 반환한다.
3. THE DNS_Resolver SHALL 각 캐시 레코드에 TTL(Time-To-Live)을 설정하며, 기본값은 600초로 한다.
4. WHEN Downloader가 URL의 호스트에 대한 IP 주소를 요청할 때, IF DNS_Resolver의 캐시에 해당 호스트의 레코드가 존재하고 조회 시점에 TTL이 만료된 경우, THEN THE DNS_Resolver SHALL 해당 레코드를 캐시에서 제거하고 신규 시스템 DNS 조회를 수행한 후 결과를 캐시에 저장하고 IP 주소를 반환한다.
5. WHEN DNS 조회가 실패할 때 (NXDOMAIN, 타임아웃, 네트워크 오류 포함), THE DNS_Resolver SHALL Downloader에 조회 실패를 나타내는 오류를 반환하며, Downloader는 해당 URL의 다운로드를 건너뛰고 실패 사유를 로그에 기록한다.

---

### 요구사항 4: robots.txt 준수

**사용자 스토리:** 학습자로서, 크롤러가 robots.txt를 자동으로 준수하는 과정을 확인하고 싶다. 그래야 웹 크롤러 에티켓의 기술적 구현 방식을 이해할 수 있다.

#### 인수 기준

1. WHEN Downloader가 특정 도메인의 URL을 처음 크롤링하기 전에, THE Downloader SHALL 해당 도메인의 robots.txt 파일을 `{스킴}://{도메인}/robots.txt` 경로에서 요청하고 결과를 Robots_txt_Cache에 저장한다.
2. WHEN Downloader가 URL을 크롤링하기 전에, IF Robots_txt_Cache에 해당 도메인의 robots.txt가 이미 존재하는 경우, THEN THE Downloader SHALL 추가 HTTP 요청 없이 캐시된 규칙을 사용한다.
3. WHEN robots.txt의 `User-agent: *` 섹션이 특정 경로에 대해 `Disallow` 규칙을 포함할 때, THE Downloader SHALL 해당 경로로 시작하는(prefix 매칭) URL의 다운로드를 건너뛴다.
4. WHEN robots.txt 파일이 존재하지 않을 때(HTTP 401·403·5xx를 제외한 200 이외의 응답, 예: 404, 410), THE Downloader SHALL 해당 도메인에 대해 모든 URL 크롤링을 허용하는 빈 규칙을 Robots_txt_Cache에 저장하고 크롤링을 진행한다.
5. WHEN robots.txt 요청이 401, 403, 5xx 응답을 받거나 네트워크 오류로 실패할 때, THE Downloader SHALL 해당 도메인에 대해 모든 URL 크롤링을 금지하는 규칙을 Robots_txt_Cache에 저장하고 경고를 기록한다. 이는 크롤링을 허락받지 못한 상태이기 때문이다.
6. WHEN robots.txt의 `User-agent: *` 섹션이 `Crawl-delay` 지시어를 포함할 때, THE Downloader SHALL 해당 값(초 단위, 최대 300초)을 해당 도메인의 Politeness_Delay로 사용하며, 이 값은 설정된 기본 Politeness_Delay보다 우선한다.

---

### 요구사항 5: HTML 다운로드 및 예외 처리

**사용자 스토리:** 학습자로서, 크롤러가 네트워크 오류와 타임아웃을 안정적으로 처리하는 방식을 확인하고 싶다. 그래야 실제 환경에서 발생하는 예외 상황에 대한 대처 방식을 이해할 수 있다.

#### 인수 기준

1. WHEN Downloader가 URL을 요청할 때, THE Downloader SHALL HTTP GET 요청에 30초 타임아웃을 적용한다.
2. WHEN HTTP 응답 상태 코드가 200일 때, THE Downloader SHALL 응답 본문을 Content_Parser로 전달한다.
3. WHEN HTTP 응답 상태 코드가 301 또는 302일 때, THE Downloader SHALL 응답 헤더의 `Location` 값을 새로운 URL로 URL_Frontier에 삽입하고 원본 URL 처리를 종료하며, 리다이렉트가 5회를 초과할 경우 오류를 기록하고 처리를 중단한다.
4. WHEN HTTP 응답 상태 코드가 4xx일 때, THE Downloader SHALL 해당 URL을 Visited_URL_Store에 기록하고 처리를 건너뛴다.
5. WHEN HTTP 응답 상태 코드가 500 이상이거나 타임아웃이 발생할 때, THE Downloader SHALL 해당 URL을 5초 간격으로 최대 2회까지 재시도하고, 재시도 후에도 실패하면 오류를 기록하고 건너뛴다.
6. WHEN HTTP 응답의 Content-Type이 `text/html`이 아닐 때, THE Downloader SHALL 해당 응답 본문을 Content_Parser로 전달하지 않고 건너뛴다.
7. WHEN HTTP 응답에 Content-Type 헤더가 없을 때, THE Downloader SHALL 해당 응답 본문을 Content_Parser로 전달하지 않고 건너뛴다.

---

### 요구사항 6: 콘텐츠 파싱 및 URL 추출

**사용자 스토리:** 학습자로서, HTML에서 링크와 텍스트를 추출하는 파이프라인을 확인하고 싶다. 그래야 콘텐츠 파서의 역할과 데이터 노이즈 제거 방식을 이해할 수 있다.

#### 인수 기준

1. WHEN Content_Parser가 `<title>` 태그를 포함한 HTML 문자열을 입력으로 받을 때, THE Content_Parser SHALL `<title>` 태그의 텍스트 내용을 페이지 제목으로 추출한다.
2. IF Content_Parser가 입력받은 HTML에 `<title>` 태그가 없거나 `<title>` 태그의 텍스트 내용이 비어 있을 때, THEN THE Content_Parser SHALL `title` 필드에 빈 문자열(`""`)을 반환한다.
3. WHEN Content_Parser가 HTML을 파싱할 때, THE Content_Parser SHALL `<script>`, `<style>`, `<nav>`, `<footer>` 태그와 그 하위 내용을 제거한 후, 나머지 태그의 텍스트 노드를 공백 문자(스페이스, 탭, 개행)로 구분하여 하나의 문자열로 연결한 결과를 본문(`body_text`)으로 추출한다.
4. WHEN Content_Parser가 HTML을 파싱할 때, THE Content_Parser SHALL `http://` 또는 `https://`로 시작하거나 `/`, `./`, `../`로 시작하는 `href` 속성 값을 가진 모든 `<a>` 태그에서 URL을 추출하며, `javascript:`, `mailto:`, `#`으로 시작하는 `href` 값은 추출 대상에서 제외한다.
5. WHEN 추출된 URL이 `/`, `./`, `../`로 시작하는 상대 경로일 때, THE Content_Parser SHALL 입력으로 함께 제공된 현재 페이지의 절대 URL(기준 URL)을 기준으로 절대 경로로 변환한다.
6. IF 상대 경로 URL 변환 시 기준 URL이 제공되지 않았을 때, THEN THE Content_Parser SHALL 해당 상대 경로 URL을 `extracted_urls` 목록에서 제외한다.
7. THE Content_Parser SHALL 파싱 결과로 `{url, title, body_text, extracted_urls}` 구조의 객체를 반환하며, `url` 필드에는 파싱 호출 시 입력으로 제공된 기준 URL을 그대로 담는다.
8. IF HTML 파싱 중 예외가 발생할 때, THEN THE Content_Parser SHALL 오류를 기록하고 `{url: 입력_기준_URL, title: "", body_text: "", extracted_urls: []}` 구조의 객체를 반환한다.

---

### 요구사항 7: 중복 콘텐츠 감지

**사용자 스토리:** 학습자로서, MD5 해시를 이용해 중복 페이지를 감지하는 원리를 직접 확인하고 싶다. 그래야 콘텐츠 중복 제거의 구현 방식을 이해할 수 있다.

#### 인수 기준

1. WHEN Content_Parser가 본문 텍스트를 추출한 후, THE Duplicate_Detector SHALL HTML 태그와 앞뒤 공백을 제거한 본문 텍스트의 MD5 해시를 계산한다.
2. IF 계산된 MD5 해시가 이미 Content_Store에 존재하는 경우, THEN THE Duplicate_Detector SHALL 해당 페이지를 중복으로 판정하고 Content_Store에 저장하지 않는다.
3. IF 계산된 MD5 해시가 Content_Store에 존재하지 않는 경우, THEN THE Duplicate_Detector SHALL 해당 해시를 URL과 함께 기록하고 페이지를 Content_Store에 저장하도록 허용한다.
4. WHEN 본문 텍스트가 비어 있을 때, THE Duplicate_Detector SHALL 해당 페이지를 중복이 아닌 빈 콘텐츠로 표시하여 Content_Store에 저장하도록 허용한다.
5. WHEN Duplicate_Detector가 중복 여부를 판정할 때, THE Duplicate_Detector SHALL URL, MD5 해시 값, 판정 결과(중복/신규/빈 콘텐츠)를 출력한다.

---

### 요구사항 8: URL 필터링 및 크롤러 트랩 방지

**사용자 스토리:** 학습자로서, 크롤러 트랩을 방지하는 URL 필터링 로직을 확인하고 싶다. 그래야 무한 루프 크롤링을 방어하는 설계 원리를 이해할 수 있다.

#### 인수 기준

1. WHEN URL_Filter가 URL을 평가할 때, IF URL 길이가 2,048자를 초과하는 경우, THEN THE URL_Filter SHALL 해당 URL을 거부한다.
2. WHEN URL_Filter가 URL을 평가할 때, IF 해당 URL의 Crawl_Depth가 설정된 최대 크롤링 깊이를 초과하는 경우, THEN THE URL_Filter SHALL 해당 URL을 거부한다.
3. WHEN URL_Filter가 URL을 평가할 때, IF URL 경로에 동일한 세그먼트가 대소문자 구분 없이 3회 이상 반복되는 경우 (예: `/a/b/a/b/a`), THEN THE URL_Filter SHALL 해당 URL을 거부한다.
4. WHEN URL_Filter가 URL을 평가할 때, IF URL의 스킴(scheme)이 `http` 또는 `https`가 아닌 경우, THEN THE URL_Filter SHALL 해당 URL을 거부한다.
5. WHEN URL_Filter가 URL을 평가할 때, IF URL이 Visited_URL_Store에 이미 존재하는 경우, THEN THE URL_Filter SHALL 해당 URL을 거부한다.
6. WHEN URL_Filter가 URL을 거부할 때, THE URL_Filter SHALL 거부된 URL과 거부 사유(길이 초과/깊이 초과/경로 반복/스킴 오류/이미 방문)를 로그에 기록한다.
7. WHEN URL_Filter가 하나의 URL에서 여러 규칙을 동시에 위반할 때, THE URL_Filter SHALL 첫 번째로 감지된 위반 사유만 로그에 기록하고 해당 URL을 거부한다.
8. WHEN URL_Filter가 http 또는 https URL을 평가할 때, IF URL 파서(urlparse)와 HTTP 클라이언트(urllib3)가 해석한 호스트가 서로 다르거나(예: `http://evil.com\@a.com/`) 호스트를 얻을 수 없는 경우, THEN THE URL_Filter SHALL 해당 URL을 형식 오류로 거부한다. 이는 범위 판정, robots.txt, DNS 조회가 실제 접속 호스트와 다른 호스트를 보지 않게 하기 위함이다. 대소문자, IPv6 대괄호, IDN 표기 차이는 같은 호스트로 본다.

---

### 요구사항 9: 방문 URL 저장소 관리

**사용자 스토리:** 학습자로서, 방문한 URL을 해시 테이블로 관리하는 원리를 확인하고 싶다. 그래야 O(1) 중복 체크 방식을 이해할 수 있다.

#### 인수 기준

1. THE Visited_URL_Store SHALL 방문한 URL을 해시 테이블에 저장하여 O(1) 시간 복잡도로 URL 존재 여부를 조회한다.
2. WHEN HTTP 응답 상태 코드가 200이고 다운로드가 성공적으로 완료되었을 때, THE Visited_URL_Store SHALL 해당 URL을 저장한다.
3. WHEN HTTP 응답 상태 코드가 4xx이거나 최대 재시도 횟수(2회)를 초과하여 실패했을 때, THE Visited_URL_Store SHALL 해당 URL을 저장하여 재방문을 방지한다.
4. WHEN 이미 Visited_URL_Store에 존재하는 URL이 다시 삽입될 때, THE Visited_URL_Store SHALL 해당 삽입을 무시하고 기존 항목을 유지한다.
5. WHEN URL_Filter 또는 Downloader가 특정 URL의 방문 여부를 조회할 때, THE Visited_URL_Store SHALL 해당 URL의 존재 여부를 boolean 값으로 반환한다.
6. THE Visited_URL_Store SHALL 저장된 URL의 총 개수를 정수로 반환하는 기능을 제공한다.

---

### 요구사항 10: BFS 기반 크롤링 오케스트레이션

**사용자 스토리:** 학습자로서, BFS 방식으로 웹 페이지를 탐색하는 전체 흐름을 코드로 확인하고 싶다. 그래야 DFS와의 차이점 및 BFS를 선택한 이유를 실제로 체감할 수 있다.

#### 인수 기준

1. THE Crawler SHALL URL_Frontier에서 URL을 꺼내고, 다운로드하고, 파싱하고, 추출된 URL을 다시 URL_Frontier에 삽입하는 BFS 루프를 실행한다.
2. WHEN Crawler의 BFS 루프가 실행되는 동안, THE Crawler SHALL 깊이 N의 모든 URL 처리가 완료된 후에만 깊이 N+1의 URL 처리를 시작한다.
3. WHEN Content_Store에 저장된 페이지 수가 설정된 최대 페이지 수에 도달할 때, THE Crawler SHALL BFS 루프를 즉시 종료한다.
4. WHEN URL_Frontier가 비어 있을 때, THE Crawler SHALL BFS 루프를 정상 종료한다.
5. WHEN Content_Parser가 URL을 추출할 때, THE Crawler SHALL 각 추출된 URL에 현재 페이지의 Crawl_Depth에 1을 더한 값을 부여한 후 URL_Filter를 통과한 URL만 URL_Frontier에 삽입한다. 단, 현재 페이지의 Crawl_Depth가 최대 크롤링 깊이와 같으면 추출된 URL은 어차피 깊이 초과로 거부되므로 URL_Filter에 넘기지 않고 삽입을 건너뛰며, 이 URL들은 건너뛴 URL 수와 거부 로그에 포함하지 않는다.
6. THE Crawler SHALL 크롤링 세션 종료 후 표준 출력으로 총 수집 페이지 수(Content_Store 저장 수), URL_Filter 및 Downloader에서 건너뛴 URL 수의 합산, 중복 감지 수, 범위 밖 링크 수, 소요 시간(초 단위)을 포함한 요약 통계를 출력한다.
7. THE Crawler SHALL 기본적으로 Seed_URL과 정확히 같은 호스트의 URL만 크롤링한다. 허용 도메인이 지정되면 그 도메인과 모든 하위 도메인을 추가로 허용하고, 전체 허용 옵션이 켜지면 호스트를 제한하지 않는다. 범위 밖 링크는 URL_Frontier에 삽입하지 않고 경고 없이 무시하며 건너뛴 URL 수가 아닌 범위 밖 링크 수로 따로 집계한다. 호스트를 알 수 없는 URL(형식 오류)은 범위 판정 대상이 아니며 URL_Filter가 거부한다. Seed_URL은 항상 범위 안이며 시드가 여러 개이면 각 시드 호스트의 합집합이 범위이다. 리다이렉트 대상도 추출된 링크와 같은 범위 판정을 받는다.

---

### 요구사항 11: 콘텐츠 저장소

**사용자 스토리:** 학습자로서, 수집된 페이지 데이터를 구조화하여 저장하고 조회하는 방법을 확인하고 싶다. 그래야 크롤링 결과물의 활용 방법을 이해할 수 있다.

#### 인수 기준

1. WHEN Duplicate_Detector가 페이지 저장을 허용할 때, THE Content_Store SHALL 각 페이지를 `{url, title, body_text, extracted_urls, crawled_at, md5_hash, products}` 구조로 저장하며, 동일 URL이 재저장될 경우 기존 항목을 덮어쓴다.
2. WHEN Content_Store에 페이지가 저장될 때, THE Content_Store SHALL 저장 시각(crawled_at)을 UTC 기준 ISO 8601 형식으로 기록한다.
3. WHEN URL을 키로 페이지를 조회할 때, THE Content_Store SHALL 저장된 페이지를 O(1)로 반환하며, URL이 존재하지 않으면 해당 URL이 없음을 나타내는 값(null 또는 None)을 반환한다.
4. THE Content_Store SHALL 저장된 모든 페이지의 URL 목록을 순서 없이 반환하는 기능을 제공한다.
5. WHERE 파일 저장 옵션이 활성화된 경우, THE Content_Store SHALL 크롤링 세션 종료 시 최대 10,000개 레코드를 JSON Lines 형식의 파일로 저장한다.
6. WHEN 파일 저장 중 오류가 발생할 때, THE Content_Store SHALL 오류 원인을 로그에 기록하고 요약 통계에 저장 실패를 반영한다.

---

### 요구사항 12: 사이트별 상품 추출

**사용자 스토리:** 학습자로서, 범용 본문 텍스트에 섞이는 메뉴와 다른 상품 정보 대신 상품명과 가격을 구조화해서 얻고 싶다. 그래야 크롤링 결과를 실제 데이터로 활용할 수 있다.

#### 인수 기준

1. WHERE 추출기가 지정된 경우, THE Crawler SHALL 저장이 허용된 각 페이지의 HTML에서 지정된 사이트별 추출기로 `{pcode, name, option, price, url}` 구조의 상품 목록을 추출해 페이지와 함께 저장한다. 추출기가 지정되지 않으면 상품 목록은 빈 목록이다.
2. THE 추출기 SHALL 사이트가 자주 바꾸는 스타일 유틸리티 클래스가 아니라 의미 있는 카드 클래스와 접근성 속성(aria-label)에 기대어 상품을 식별한다.
3. THE 추출기 SHALL 상품 식별자(pcode)가 없는 광고 링크와, 이름이나 가격이 없는 카드를 결과에서 제외하고, 같은 pcode는 한 번만 보고한다.
4. IF 추출 중 예외가 발생할 때, THEN THE Crawler SHALL 오류와 원인을 로그에 기록하고 상품 없이 페이지 저장을 계속한다.
5. WHERE 추출기가 지정된 경우, THE Crawler SHALL 요약 통계에 추출한 상품 수를 포함해 출력한다.
