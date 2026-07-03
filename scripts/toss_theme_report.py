#!/usr/bin/env python3
"""
Toss Securities (토스증권) surge-ranking + theme report. No auth/cookies needed —
uses the same public JSON APIs the WTS web app (wts.tossinvest.com) calls.

Usage:
    python scripts/toss_theme_report.py                        # KR 급등주 + 핫테마
    python scripts/toss_theme_report.py --market us            # US 급등주
    python scripts/toss_theme_report.py --rank biggest_total_amount   # 토스 거래대금 랭킹
    python scripts/toss_theme_report.py --themes 8 --theme-stocks 6

Data:
  - 급등 랭킹      : POST wts-cert-api /api/v2/dashboard/wts/overview/ranking (id=heavy_soar)
  - 테마 등락 전체 : GET  wts-info-api /api/v1/tics/all  (TICS = 토스 테마 분류)
  - 테마 소속 종목 : POST wts-info-api /api/v2/tics/{id}/stocks

Outputs a console digest + JSON (default: toss_theme_<market>.json) for app/LLM use.
⚠️ 비공식(웹 내부) API — 과도한 호출 금지, 스키마는 예고 없이 바뀔 수 있음.
"""
from __future__ import annotations
import argparse, json, sys, urllib.request
from collections import defaultdict
from pathlib import Path

CERT = "https://wts-cert-api.tossinvest.com"
INFO = "https://wts-info-api.tossinvest.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# rankingId → 지원 duration (dashboard.bad-request 회피용 기본값)
RANK_DURATION = {"heavy_soar": "1d", "biggest_total_amount": "realtime"}


def _http(url: str, body: dict | None = None, timeout: int = 25):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def _pct(base, close) -> float | None:
    if not base:
        return None
    return round((close - base) / base * 100, 2)


# ── 1) 급등/거래대금 랭킹 ────────────────────────────────────────────
def fetch_ranking(rank_id: str, market: str, duration: str | None) -> list[dict]:
    body = {"id": rank_id, "tag": market,
            "duration": duration or RANK_DURATION.get(rank_id, "1d"),
            "filters": []}
    raw = _http(f"{CERT}/api/v2/dashboard/wts/overview/ranking", body)
    rows = []
    for p in (raw.get("result") or {}).get("products", []):
        price = p.get("price") or {}
        tics = p.get("primaryTics") or {}
        rows.append({
            "rank": p.get("rank"),
            "code": p.get("productCode"),
            "name": p.get("name"),
            "close": price.get("close"),
            "change_pct": _pct(price.get("base"), price.get("close")),
            "volume": price.get("marketVolume") or price.get("tossSecuritiesVolume"),
            "amount": price.get("marketAmount") or price.get("tossSecuritiesAmount"),
            "market_cap_krw": p.get("marketCapKrw"),
            "theme_id": tics.get("ticsId"),
            "theme": tics.get("name"),
        })
    return rows


# ── 2) 전체 테마(TICS) 등락 ──────────────────────────────────────────
def fetch_theme_fluctuations() -> list[dict]:
    raw = _http(f"{INFO}/api/v1/tics/all")
    themes = []

    def walk(items):
        for it in items or []:
            fl = it.get("fluctuations") or {}
            if fl.get("oneDayRate") is not None:
                themes.append({
                    "theme_id": it.get("id"), "theme": it.get("title"),
                    "depth": it.get("depth"), "companies": it.get("companyCount"),
                    "one_day_pct": fl.get("oneDayRate"),
                })
            walk(it.get("subItems"))

    walk((raw.get("result") or {}).get("ticsItems"))
    return themes


# ── 3) 테마 소속 종목 ────────────────────────────────────────────────
def fetch_theme_stocks(theme_id: int, limit: int) -> list[dict]:
    raw = _http(f"{INFO}/api/v2/tics/{theme_id}/stocks", body={})
    rows = []
    for s in (raw.get("result") or {}).get("stocks", [])[:limit]:
        rows.append({
            "code": s.get("code"), "name": s.get("name"),
            "change_pct": round((s.get("changeRate") or 0) * 100, 2),
            "market_cap_krw": s.get("marketCapKrw"),
        })
    return rows


def hot_themes_from_ranking(rows: list[dict]) -> list[dict]:
    """급등 랭킹 종목들을 테마로 묶어 '지금 뜨는 테마'를 만든다."""
    buckets: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        if r["theme_id"]:
            buckets[(r["theme_id"], r["theme"])].append(r)
    out = []
    for (tid, name), members in buckets.items():
        pcts = [m["change_pct"] for m in members if m["change_pct"] is not None]
        out.append({
            "theme_id": tid, "theme": name, "count": len(members),
            "avg_change_pct": round(sum(pcts) / len(pcts), 2) if pcts else None,
            "stocks": [m["name"] for m in members],
        })
    out.sort(key=lambda t: (t["count"], t["avg_change_pct"] or 0), reverse=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="토스증권 급등주 + 테마 리포트")
    ap.add_argument("--market", default="kr", choices=["kr", "us"])
    ap.add_argument("--rank", default="heavy_soar",
                    help="rankingId: heavy_soar(급등)·biggest_total_amount(토스 거래대금) 등")
    ap.add_argument("--duration", default=None, help="realtime / 1d (기본: id별 자동)")
    ap.add_argument("--limit", type=int, default=20, help="랭킹 표시 종목 수")
    ap.add_argument("--themes", type=int, default=5, help="상세 조회할 핫테마 수")
    ap.add_argument("--theme-stocks", type=int, default=5, help="테마당 소속 종목 표시 수")
    ap.add_argument("--out", default=None, help="JSON 출력 경로")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ranking = fetch_ranking(args.rank, args.market, args.duration)[: args.limit]
    hot = hot_themes_from_ranking(ranking)
    all_themes = fetch_theme_fluctuations()
    leaf = [t for t in all_themes if t["depth"] and t["depth"] > 0] or all_themes
    top_themes = sorted(leaf, key=lambda t: t["one_day_pct"], reverse=True)

    for t in hot[: args.themes]:
        try:
            t["members"] = fetch_theme_stocks(t["theme_id"], args.theme_stocks)
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] theme {t['theme_id']} stocks failed: {e}", file=sys.stderr)

    # ── digest ──
    label = "급등" if args.rank == "heavy_soar" else args.rank
    print(f"\n=== 토스증권 {args.market.upper()} {label} 랭킹 TOP {len(ranking)} ===")
    for r in ranking:
        pct = f"{r['change_pct']:+.2f}%" if r["change_pct"] is not None else "  n/a "
        theme = f"  [{r['theme']}]" if r["theme"] else ""
        print(f"{r['rank']:>3}. {r['name']:<14} {pct:>8}{theme}")

    print(f"\n=== 급등주 기준 핫테마 ===")
    for t in hot[: args.themes]:
        avg = f"평균 {t['avg_change_pct']:+.2f}%" if t["avg_change_pct"] is not None else ""
        print(f"● {t['theme']} — 급등 {t['count']}종목 {avg}  ({', '.join(t['stocks'][:5])})")
        for m in t.get("members", []):
            print(f"    - {m['name']:<14} {m['change_pct']:+.2f}%")

    print(f"\n=== 전체 테마 등락 TOP 10 (1일) ===")
    for t in top_themes[:10]:
        print(f"  {t['one_day_pct']:+6.2f}%  {t['theme']} ({t['companies']}종목)")
    print(f"\n=== 전체 테마 등락 BOTTOM 5 (1일) ===")
    for t in top_themes[-5:]:
        print(f"  {t['one_day_pct']:+6.2f}%  {t['theme']} ({t['companies']}종목)")

    out_path = Path(args.out or f"toss_theme_{args.market}.json")
    out_path.write_text(json.dumps({
        "source": "tossinvest-web-api", "market": args.market, "rank_id": args.rank,
        "ranking": ranking, "hot_themes": hot[: args.themes],
        "theme_fluctuations_top": top_themes[:20],
        "theme_fluctuations_bottom": top_themes[-10:],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[saved] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
