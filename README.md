# claudecodejules89 — 소셜/뉴스 종목 리서치 툴킷

여러 플랫폼(X·Reddit·StockTwits·雪球·小红书·Facebook·Instagram + 뉴스/웹 검색)에서
**종목·테마별 소셜 여론과 시세를 실시간으로 수집**하기 위한 개인 리서치 세팅.

에이전트가 각 상단 도구(twitter-cli·rdt-cli·OpenCLI·gh·Exa 등)를 직접 호출하는 구조이며,
이 저장소는 **통합 스크립트 + 설정 + 세팅 문서**를 담습니다.

## 무엇이 되나

| 분류 | 채널 | 방식 |
|---|---|---|
| **소셜** | X/Twitter, Reddit, StockTwits | CLI + 쿠키 / 공개 API |
| **중국** | 雪球(시세·핫종목·K선), 小红书, Weibo 등 | OpenCLI |
| **소셜(글로벌)** | Facebook, Instagram | OpenCLI |
| **뉴스/검색** | Exa 전역검색, 네이버뉴스, 웹(Jina) | MCP / API |
| **기타** | YouTube, RSS, V2EX, B站, GitHub, 小宇宙(전사) | 각 도구 |

## 대표 기능: 통합 소셜 리포트
티커 하나로 X·Reddit·StockTwits를 한 번에 수집·정규화 (StockTwits 네이티브 감성 포함).
```bash
python scripts/social_report.py O "Realty Income" --days 2 --limit 12
```
출력: 콘솔 다이제스트 + `social_<TICKER>.json` (앱/다른 도구 연동용).

## 대표 기능: 실시간 시세 (신선도 보장)
기억/추정으로 답하지 않고 **매번 토스 API로 조회 + 데이터 체결시각 표시 + 10분 초과 시 STALE 경고**.
```bash
python scripts/quote.py 삼성전자 SK하이닉스 카카오   # 이름(별칭) 또는 6자리 코드
python scripts/quote.py 005930 --quotes            # 호가창 10단계까지
python scripts/quote.py 005930 --json --max-age 5  # JSON, 5분 초과면 STALE
```
exit code: `0`=최신 · `3`=STALE(오래됨) · `4`=조회실패/미발견 → 스크립트/에이전트가 오래된 값을 신뢰하지 않도록 강제.

## 대표 기능: 토스증권 급등주 + 테마 리포트
토스증권 웹(WTS)이 쓰는 공개 JSON API로 **급등 랭킹 → 테마 집계 → 테마별 소속 종목·전체 테마 등락**을 한 번에. 인증/쿠키 불필요.
```bash
python scripts/toss_theme_report.py                      # KR 급등주 + 핫테마
python scripts/toss_theme_report.py --market us          # 미국 급등주
python scripts/toss_theme_report.py --rank biggest_total_amount  # 토스 거래대금 랭킹
```
출력: 콘솔 다이제스트 + `toss_theme_<market>.json`.
⚠️ 비공식(웹 내부) API — 과도한 호출 금지, 스키마 변경 가능. 공식 Open API(주문 등)와는 별개.

## 구조
```
scripts/social_report.py      # X + Reddit + StockTwits 통합 리포트
scripts/quote.py              # 토스증권 실시간 시세 (체결시각·STALE 경고)
scripts/toss_theme_report.py  # 토스증권 급등 랭킹 + 테마(TICS) 리포트
config/mcporter.json          # Exa 전역검색 MCP 설정
SETUP.md                      # 새 컴퓨터 세팅 가이드 (도구 설치 + 로그인)
.gitignore                    # 쿠키/자격증명/venv 차단
```

## 시작하기
1. 다른 컴퓨터에서 쓰려면 **[SETUP.md](SETUP.md)** 를 따라 도구 설치 + 로그인 (git으로는 코드만 옴)
2. 쿠키·API 키·로그인은 **컴퓨터마다** 따로 등록 — 보안상 저장소엔 절대 커밋하지 않음

## ⚠️ 주의
- 쿠키/로그인은 계정 권한 전체 → 스크립트 접근 시 정지 위험, **부계정 권장**
- Windows 실행 시 UTF-8 필요: `export PYTHONUTF8=1 PYTHONIOENCODING=utf-8`
- 자격증명은 홈 폴더(`~/.config`, `~/.agent-reach`)와 브라우저 프로필에만 저장
