#!/usr/bin/env python3
"""
토스증권 실시간 시세 조회 — '무조건 최신값' 보장 도구.

핵심 원칙(이 스크립트는 절대 기억/추정으로 답하지 않음):
  1) 호출 시점마다 토스 웹 API에서 실시간 조회
  2) 데이터에 찍힌 체결시각(tradeDateTime)을 함께 출력 → 언제 값인지 명확
  3) 조회 실패 시 값을 내놓지 않고 에러로 종료(exit!=0)
  4) 데이터가 --max-age(기본 10분)보다 오래됐으면 ⚠️ STALE 경고

Usage:
    python scripts/quote.py 005930 000660        # 코드로
    python scripts/quote.py 삼성전자 SK하이닉스 카카오   # 이름(별칭)으로
    python scripts/quote.py 005930 --quotes       # 호가창까지
    python scripts/quote.py 005930 --json         # JSON만 출력
    python scripts/quote.py 005930 --max-age 5    # 5분 초과면 STALE

exit code: 0=정상(최신), 3=STALE(오래됨), 4=조회 실패/미발견
"""
from __future__ import annotations
import argparse, json, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

INFO = "https://wts-info-api.tossinvest.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
KST = timezone(timedelta(hours=9))

# 자주 쓰는 종목 별칭 (그 외는 6자리 코드로 입력)
ALIASES = {
    "삼성전자": "005930", "삼전": "005930", "sk하이닉스": "000660", "하이닉스": "000660",
    "sk스퀘어": "402340", "lg에너지솔루션": "373220", "엘지엔솔": "373220", "삼성바이오로직스": "207940",
    "현대차": "005380", "기아": "000270", "네이버": "035420", "naver": "035420",
    "카카오": "035720", "삼성sdi": "006400", "lg화학": "051910", "셀트리온": "068270",
    "포스코홀딩스": "005490", "posco": "005490", "kb금융": "105560", "신한지주": "055550",
    "하나금융지주": "086790", "현대모비스": "012330", "삼성물산": "028260", "삼성생명": "032830",
    "sk이노베이션": "096770", "한화에어로스페이스": "012450", "두산에너빌리티": "034020",
    "삼성전기": "009150", "고려아연": "010130", "hd현대중공업": "329180", "크래프톤": "259960",
    "삼성증권": "016360", "미래에셋증권": "006800", "키움증권": "039490", "한미반도체": "042700",
    "에코프로비엠": "247540", "에코프로": "086520", "포스코퓨처엠": "003670", "알테오젠": "196170",
    "hlb": "028300", "엔씨소프트": "036570", "카카오뱅크": "323410", "kt": "030200",
    "sk텔레콤": "017670", "lg전자": "066570", "한국전력": "015760",
}


def norm_code(token: str) -> str | None:
    """입력을 A붙은 productCode로 정규화. 이름이면 별칭표에서 코드 조회."""
    t = token.strip()
    body = t[1:] if (t[:1] in "Aa" and t[1:].isdigit()) else t
    if body.isdigit() and len(body) == 6:
        return "A" + body
    code = ALIASES.get(t.lower())
    return "A" + code if code else None


def _get(url: str, timeout: int = 15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def fetch_prices(codes: list[str]) -> dict[str, dict]:
    joined = ",".join(codes)
    raw = _get(f"{INFO}/api/v3/stock-prices/details?productCodes={joined}")
    return {r["code"]: r for r in (raw.get("result") or [])}


def fetch_name(code: str) -> str:
    try:
        raw = _get(f"{INFO}/api/v2/stock-infos/{code}")
        return (raw.get("result") or {}).get("name") or code
    except Exception:  # noqa: BLE001
        return code


def fetch_quotes(code: str) -> dict | None:
    try:
        raw = _get(f"{INFO}/api/v3/stock-prices/{code}/quotes")
        return raw.get("result")
    except Exception:  # noqa: BLE001
        return None


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="토스증권 실시간 시세 (신선도 보장)")
    ap.add_argument("tickers", nargs="+", help="6자리 코드 또는 등록된 종목명")
    ap.add_argument("--quotes", action="store_true", help="호가창 10단계 표시")
    ap.add_argument("--max-age", type=float, default=10.0, help="STALE 판정 분(기본 10)")
    ap.add_argument("--json", action="store_true", help="JSON만 출력")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    codes, unknown = [], []
    for t in args.tickers:
        c = norm_code(t)
        (codes.append(c) if c else unknown.append(t))
    if unknown:
        print(f"❌ 코드로 변환 불가(6자리 코드로 입력하세요): {', '.join(unknown)}",
              file=sys.stderr)
    if not codes:
        return 4

    now = datetime.now(timezone.utc)
    try:
        prices = fetch_prices(codes)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"❌ 시세 조회 실패 — 값을 제공하지 않습니다: {e}", file=sys.stderr)
        return 4

    rows, worst_age, any_missing = [], 0.0, bool(unknown)
    for code in codes:
        p = prices.get(code)
        if not p:
            print(f"❌ {code}: 데이터 없음(상장폐지/코드오류?)", file=sys.stderr)
            any_missing = True
            continue
        dt = parse_dt(p.get("tradeDateTime"))
        age_min = (now - dt).total_seconds() / 60 if dt else None
        if age_min is not None:
            worst_age = max(worst_age, age_min)
        base, close = p.get("base"), p.get("close")
        pct = round((close - base) / base * 100, 2) if base else None
        rows.append({
            "code": code, "name": fetch_name(code),
            "close": close, "base": base, "change_pct": pct,
            "open": p.get("open"), "high": p.get("high"), "low": p.get("low"),
            "volume": p.get("volume"), "value": p.get("value"),
            "market_cap": p.get("marketCap"),
            "upper_limit": p.get("upperLimit"), "lower_limit": p.get("lowerLimit"),
            "trade_time_utc": p.get("tradeDateTime"),
            "trade_time_kst": dt.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S") if dt else None,
            "age_minutes": round(age_min, 2) if age_min is not None else None,
            "quotes": fetch_quotes(code) if args.quotes else None,
        })

    stale = worst_age > args.max_age
    fetched_kst = now.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S")

    if args.json:
        print(json.dumps({
            "fetched_at_kst": fetched_kst, "max_age_min": args.max_age,
            "stale": stale, "worst_age_min": round(worst_age, 2), "rows": rows,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n📡 조회시각(KST): {fetched_kst}   |   데이터 최신도: "
              f"최대 {worst_age:.1f}분 전  "
              f"{'⚠️  STALE(오래됨)' if stale else '✅ 신선'}")
        print("─" * 62)
        for r in rows:
            pct = f"{r['change_pct']:+.2f}%" if r["change_pct"] is not None else " n/a"
            age = f"{r['age_minutes']:.1f}분전" if r["age_minutes"] is not None else "?"
            print(f"{r['name']:<12}({r['code']})  {r['close']:>12,}원  {pct:>8}   "
                  f"[체결 {r['trade_time_kst']} · {age}]")
            if args.quotes and r["quotes"]:
                q = r["quotes"]
                offs = list(zip(q.get("offerPrices", []), q.get("offerVolumes", [])))
                bids = list(zip(q.get("bidPrices", []), q.get("bidVolumes", [])))
                print("    매도호가:", "  ".join(f"{p:,}({v:,})" for p, v in offs[:5]))
                print("    매수호가:", "  ".join(f"{p:,}({v:,})" for p, v in bids[:5]))
        if stale:
            print(f"\n⚠️  가장 오래된 데이터가 {worst_age:.1f}분 전입니다 "
                  f"(기준 {args.max_age:.0f}분). 장 마감/휴장이면 정상일 수 있어요.")

    if any_missing:
        return 4
    return 3 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
