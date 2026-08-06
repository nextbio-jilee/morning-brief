"""시장 데이터 수집 — API 키는 환경변수(GitHub Secrets)에서만 읽는다."""
import os, json, time, datetime, urllib.request, urllib.parse

AV = os.environ.get("ALPHAVANTAGE_KEY", "")
FMP = os.environ.get("FMP_KEY", "")
FINNHUB = os.environ.get("FINNHUB_KEY", "")
TIMEOUT = 30
AV_GAP = 13.0          # Alpha Vantage 무료 티어는 분당 5회. 호출 간격을 벌린다.
_av_last = [0.0]

HINT = {402: "플랜 제한", 403: "권한 없음", 404: "엔드포인트 없음", 429: "호출 한도 초과"}


def log(*a):
    print(*a, flush=True)


def get(url, what=""):
    safe = url.split("apikey=")[0].split("token=")[0]
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        log(f"  ! {what}: HTTP {e.code} {HINT.get(e.code, '')} — {safe}")
    except Exception as e:
        log(f"  ! {what}: {e} — {safe}")
    return None


def av(fn, what, **kw):
    """Alpha Vantage — 호출 간격을 지키고, 한도 안내가 오면 한 번 더 기다렸다 재시도."""
    if not AV:
        log(f"  - {what}: ALPHAVANTAGE_KEY 없음"); return None
    kw.update(function=fn, apikey=AV)
    url = "https://www.alphavantage.co/query?" + urllib.parse.urlencode(kw)
    for attempt in (1, 2):
        wait = max(0.0, AV_GAP - (time.time() - _av_last[0]))
        if wait:
            time.sleep(wait)
        _av_last[0] = time.time()
        d = get(url, what)
        if not isinstance(d, dict):
            return d
        msg = d.get("Note") or d.get("Information") or d.get("Error Message")
        if not msg:
            return d
        if attempt == 1 and ("sparingly" in str(msg) or "frequency" in str(msg)):
            log(f"  … {what}: 호출 한도 — 20초 후 재시도")
            time.sleep(20)
            continue
        log(f"  ! {what}: {str(msg)[:110]}")
        return None
    return None


def fmp_indices(symbols):
    """FMP는 플랜마다 열려 있는 경로가 다르다. 되는 것을 찾을 때까지 순서대로 시도한다."""
    if not FMP:
        log("  - FMP_KEY 없음"); return {}

    # 1) 배치 — 한 번의 호출로 주요 지수 전체
    d = get(f"https://financialmodelingprep.com/stable/batch-index-quotes?apikey={FMP}", "지수 배치")
    if isinstance(d, list) and d:
        found = {r.get("symbol"): r for r in d if isinstance(r, dict)}
        if any(s in found for s in symbols):
            log("  → batch-index-quotes 사용")
            return found

    # 2) 종목별 — stable / legacy v3 순서로
    out = {}
    for sym in symbols:
        enc = urllib.parse.quote(sym, safe="")
        for url, tag in [
            (f"https://financialmodelingprep.com/stable/quote?symbol={enc}&apikey={FMP}", "stable/quote"),
            (f"https://financialmodelingprep.com/api/v3/quote/{enc}?apikey={FMP}", "v3/quote"),
        ]:
            r = get(url, f"{sym} ({tag})")
            if isinstance(r, list) and r and r[0].get("price") is not None:
                out[sym] = r[0]
                log(f"  → {sym}: {tag} 사용")
                break
    return out


def last_series(payload, n=2):
    out = []
    for row in (payload or {}).get("data", []):
        v = row.get("value")
        if v not in (None, ".", ""):
            out.append({"date": row["date"], "value": float(v)})
        if len(out) == n:
            break
    return out


def pct(s):
    if len(s) < 2 or s[1]["value"] == 0:
        return None
    return round((s[0]["value"] - s[1]["value"]) / s[1]["value"] * 100, 2)


data = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "items": {}, "missing": []}

log("지수…")
LABELS = {"^IXIC": "나스닥 종합", "^NDX": "나스닥 100", "^GSPC": "S&P 500"}
quotes = fmp_indices(list(LABELS))
for sym, label in LABELS.items():
    r = quotes.get(sym)
    if r and r.get("price") is not None:
        data["items"][sym] = {"label": label, "price": r["price"],
                              "change_pct": r.get("changePercentage", r.get("changesPercentage")),
                              "prev_close": r.get("previousClose"), "source": "FMP"}
        log(f"  ✓ {label} {r['price']}")
    else:
        data["missing"].append(label)

log("환율…")
fx = av("CURRENCY_EXCHANGE_RATE", "원/달러", from_currency="USD", to_currency="KRW")
rate = (fx or {}).get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
if rate:
    data["items"]["USDKRW"] = {"label": "원/달러", "price": round(float(rate), 2), "source": "AlphaVantage"}
    log(f"  ✓ 원/달러 {round(float(rate), 2)}")
else:
    data["missing"].append("원/달러")

log("유가…")
for fn, label in [("WTI", "WTI"), ("BRENT", "브렌트유")]:
    s = last_series(av(fn, label, interval="daily"))
    if s:
        data["items"][fn] = {"label": label, "price": s[0]["value"], "as_of": s[0]["date"],
                             "change_pct": pct(s), "source": "AlphaVantage"}
        log(f"  ✓ {label} {s[0]['value']} ({s[0]['date']})")
    else:
        data["missing"].append(label)

log("커피…")
s = last_series(av("COFFEE", "아라비카 커피", interval="monthly"))
if s:
    data["items"]["COFFEE"] = {"label": "아라비카 커피(월평균)", "price": round(s[0]["value"], 2),
                               "as_of": s[0]["date"], "change_pct": pct(s), "unit": "US cents/lb",
                               "note": "월평균값이며 일간 시세가 아니다", "source": "AlphaVantage"}
    log(f"  ✓ 커피 월평균 {round(s[0]['value'], 2)} ({s[0]['date']})")
else:
    data["missing"].append("아라비카 커피 월평균")

data["missing"] += ["금 현물 일간", "아라비카 커피 일간"]

if FINNHUB:
    log("Finnhub…")
    for sym, label in [("QQQ", "QQQ(나스닥100 ETF)"), ("SPY", "SPY(S&P500 ETF)"), ("GLD", "GLD(금 ETF)")]:
        q = get(f"https://finnhub.io/api/v1/quote?symbol={sym}&token={FINNHUB}", label)
        if q and q.get("c"):
            data["items"][f"finnhub:{sym}"] = {"label": label, "price": q["c"],
                                               "change_pct": q.get("dp"), "source": "Finnhub"}
            log(f"  ✓ {label} {q['c']}")

json.dump(data, open("market.json", "w"), ensure_ascii=False, indent=2)
log(f"\n수집 {len(data['items'])}건, 미확보 {len(data['missing'])}건 → market.json")
