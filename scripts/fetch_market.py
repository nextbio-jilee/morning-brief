"""시장 데이터 수집 — API 키는 환경변수(GitHub Secrets)에서만 읽는다."""
import os, json, sys, datetime, urllib.request, urllib.parse

AV = os.environ.get("ALPHAVANTAGE_KEY", "")
FMP = os.environ.get("FMP_KEY", "")
FINNHUB = os.environ.get("FINNHUB_KEY", "")

TIMEOUT = 30


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  ! {e}", file=sys.stderr)
        return None


def av(fn, **kw):
    if not AV:
        return None
    kw.update(function=fn, apikey=AV)
    return get("https://www.alphavantage.co/query?" + urllib.parse.urlencode(kw))


def fmp(path, **kw):
    if not FMP:
        return None
    kw["apikey"] = FMP
    return get(f"https://financialmodelingprep.com/stable/{path}?" + urllib.parse.urlencode(kw))


def finnhub(path, **kw):
    if not FINNHUB:
        return None
    kw["token"] = FINNHUB
    return get(f"https://finnhub.io/api/v1/{path}?" + urllib.parse.urlencode(kw))


def last_series(payload, n=2):
    """Alpha Vantage 원자재 시계열에서 최근 n개 유효값."""
    out = []
    for row in (payload or {}).get("data", []):
        v = row.get("value")
        if v not in (None, ".", ""):
            out.append({"date": row["date"], "value": float(v)})
        if len(out) == n:
            break
    return out


def pct(series):
    if len(series) < 2 or series[1]["value"] == 0:
        return None
    return round((series[0]["value"] - series[1]["value"]) / series[1]["value"] * 100, 2)


data = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "items": {}, "missing": []}

# 지수 — FMP (검증됨: ^IXIC 정상)
print("지수…")
for sym, label in [("^IXIC", "나스닥 종합"), ("^NDX", "나스닥 100"), ("^GSPC", "S&P 500")]:
    q = fmp("quote", symbol=sym) or fmp("index-quote", symbol=sym)
    if isinstance(q, list) and q and q[0].get("price"):
        r = q[0]
        data["items"][sym] = {"label": label, "price": r["price"],
                              "change_pct": r.get("changePercentage"),
                              "prev_close": r.get("previousClose"), "source": "FMP"}
    else:
        data["missing"].append(label)

# 환율 — Alpha Vantage (검증됨)
print("환율…")
fx = av("CURRENCY_EXCHANGE_RATE", from_currency="USD", to_currency="KRW")
rate = (fx or {}).get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
if rate:
    data["items"]["USDKRW"] = {"label": "원/달러", "price": round(float(rate), 2), "source": "AlphaVantage"}
else:
    data["missing"].append("원/달러")

# 유가 — Alpha Vantage 일간 (검증됨)
print("유가…")
for fn, label in [("WTI", "WTI"), ("BRENT", "브렌트유")]:
    s = last_series(av(fn, interval="daily"))
    if s:
        data["items"][fn] = {"label": label, "price": s[0]["value"], "as_of": s[0]["date"],
                             "change_pct": pct(s), "source": "AlphaVantage"}
    else:
        data["missing"].append(label)

# 커피 — Alpha Vantage는 월간만 제공. 월간 평균임을 명시한다.
print("커피…")
s = last_series(av("COFFEE", interval="monthly"))
if s:
    data["items"]["COFFEE"] = {"label": "아라비카 커피(월평균)", "price": round(s[0]["value"], 2),
                               "as_of": s[0]["date"], "change_pct": pct(s), "unit": "US cents/lb",
                               "note": "월평균값이며 일간 시세가 아니다", "source": "AlphaVantage"}
data["missing"].append("금 현물 일간")
data["missing"].append("아라비카 커피 일간")

# Finnhub — 키가 있을 때만 (지수 보강용)
if FINNHUB:
    print("Finnhub…")
    for sym in ["QQQ", "SPY", "GLD"]:
        q = finnhub("quote", symbol=sym)
        if q and q.get("c"):
            data["items"][f"finnhub:{sym}"] = {"label": sym, "price": q["c"],
                                               "change_pct": q.get("dp"), "source": "Finnhub"}

json.dump(data, open("market.json", "w"), ensure_ascii=False, indent=2)
print(f"\n수집 {len(data['items'])}건, 미확보 {len(data['missing'])}건 → market.json")
