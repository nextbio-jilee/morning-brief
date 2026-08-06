"""시장 데이터 수집 — API 키는 환경변수(GitHub Secrets)에서만 읽는다."""
import os, json, sys, datetime, urllib.request, urllib.parse

AV = os.environ.get("ALPHAVANTAGE_KEY", "")
FMP = os.environ.get("FMP_KEY", "")
FINNHUB = os.environ.get("FINNHUB_KEY", "")
TIMEOUT = 30


def log(*a):
    print(*a, flush=True)


def get(url, what=""):
    safe = url.split("apikey=")[0].split("token=")[0]
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        hint = {402: "플랜 제한", 403: "권한 없음", 404: "엔드포인트/심볼 없음",
                429: "호출 한도 초과"}.get(e.code, "")
        log(f"  ! {what}: HTTP {e.code} {hint} — {safe}")
    except Exception as e:
        log(f"  ! {what}: {e} — {safe}")
    return None


def av(fn, what, **kw):
    if not AV:
        log(f"  - {what}: ALPHAVANTAGE_KEY 없음"); return None
    kw.update(function=fn, apikey=AV)
    d = get("https://www.alphavantage.co/query?" + urllib.parse.urlencode(kw), what)
    # Alpha Vantage는 한도 초과를 HTTP 200 + 안내문으로 돌려준다
    if isinstance(d, dict) and (note := d.get("Note") or d.get("Information")):
        log(f"  ! {what}: {str(note)[:120]}"); return None
    return d


def fmp(path, what, **kw):
    if not FMP:
        log(f"  - {what}: FMP_KEY 없음"); return None
    kw["apikey"] = FMP
    return get(f"https://financialmodelingprep.com/stable/{path}?" + urllib.parse.urlencode(kw), what)


def finnhub(path, what, **kw):
    kw["token"] = FINNHUB
    return get(f"https://finnhub.io/api/v1/{path}?" + urllib.parse.urlencode(kw), what)


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

# 지수 — FMP. 무료 플랜에서 quote는 402이므로 index-quote만 쓴다.
log("지수…")
for sym, label in [("^IXIC", "나스닥 종합"), ("^NDX", "나스닥 100"), ("^GSPC", "S&P 500")]:
    q = fmp("index-quote", f"{label}({sym})", symbol=sym)
    if isinstance(q, list) and q and q[0].get("price"):
        r = q[0]
        data["items"][sym] = {"label": label, "price": r["price"],
                              "change_pct": r.get("changePercentage"),
                              "prev_close": r.get("previousClose"), "source": "FMP"}
        log(f"  ✓ {label} {r['price']}")
    else:
        data["missing"].append(label)

# 환율 — Alpha Vantage
log("환율…")
fx = av("CURRENCY_EXCHANGE_RATE", "원/달러", from_currency="USD", to_currency="KRW")
rate = (fx or {}).get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
if rate:
    data["items"]["USDKRW"] = {"label": "원/달러", "price": round(float(rate), 2), "source": "AlphaVantage"}
    log(f"  ✓ 원/달러 {round(float(rate), 2)}")
else:
    data["missing"].append("원/달러")

# 유가 — Alpha Vantage 일간
log("유가…")
for fn, label in [("WTI", "WTI"), ("BRENT", "브렌트유")]:
    s = last_series(av(fn, label, interval="daily"))
    if s:
        data["items"][fn] = {"label": label, "price": s[0]["value"], "as_of": s[0]["date"],
                             "change_pct": pct(s), "source": "AlphaVantage"}
        log(f"  ✓ {label} {s[0]['value']} ({s[0]['date']})")
    else:
        data["missing"].append(label)

# 커피 — Alpha Vantage는 월간만. 월평균임을 명시한다.
log("커피…")
s = last_series(av("COFFEE", "아라비카 커피", interval="monthly"))
if s:
    data["items"]["COFFEE"] = {"label": "아라비카 커피(월평균)", "price": round(s[0]["value"], 2),
                               "as_of": s[0]["date"], "change_pct": pct(s), "unit": "US cents/lb",
                               "note": "월평균값이며 일간 시세가 아니다", "source": "AlphaVantage"}
    log(f"  ✓ 커피 월평균 {round(s[0]['value'], 2)} ({s[0]['date']})")

# 현재 플랜으로 확보 불가 — 웹 검색으로 채운다
data["missing"] += ["금 현물 일간", "아라비카 커피 일간"]

if FINNHUB:
    log("Finnhub…")
    for sym in ["QQQ", "SPY", "GLD"]:
        q = finnhub("quote", sym, symbol=sym)
        if q and q.get("c"):
            data["items"][f"finnhub:{sym}"] = {"label": sym, "price": q["c"],
                                               "change_pct": q.get("dp"), "source": "Finnhub"}
            log(f"  ✓ {sym} {q['c']}")

json.dump(data, open("market.json", "w"), ensure_ascii=False, indent=2)
log(f"\n수집 {len(data['items'])}건, 미확보 {len(data['missing'])}건 → market.json")
