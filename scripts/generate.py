"""market.json + 웹 검색으로 한국어 브리핑 HTML을 만들고 docs/에 저장한다."""
import os, json, html, datetime, pathlib, re
import anthropic

KST = datetime.timezone(datetime.timedelta(hours=9))
today = datetime.datetime.now(KST)
date_iso = today.strftime("%Y-%m-%d")
WD = ["월", "화", "수", "목", "금", "토", "일"][today.weekday()]
date_ko = f"{today.year}년 {today.month}월 {today.day}일 {WD}요일"

market = json.load(open("market.json", encoding="utf-8"))
docs = pathlib.Path("docs"); docs.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

def _scan(s, offset=0):
    """offset에서 시작해 문자열 리터럴을 존중하며 균형 잡힌 {...} 후보를 모은다."""
    out, depth, start_i, in_str, esc = [], 0, None, False, False
    for i in range(offset, len(s)):
        ch = s[i]
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch == "{":
            if depth == 0: start_i = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0 and start_i is not None:
                out.append(s[start_i:i + 1])
    return out


def _ok(cand):
    try:
        d = json.loads(cand)
        return d if isinstance(d, dict) and isinstance(d.get("items"), list) else None
    except Exception:
        return None


def extract_json(s):
    if not s:
        return None
    # 1) 코드펜스가 있으면 그것부터
    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S):
        if (d := _ok(m.group(1))):
            return d
    # 2) 전체 스캔 (뒤에서부터 — 최종 답변이 뒤에 있다)
    for cand in reversed(_scan(s)):
        if (d := _ok(cand)):
            return d
    # 3) 복구: 앞선 턴의 조각 때문에 따옴표 짝이 어긋난 경우,
    #    "headline" 키가 나오는 지점마다 새로 스캔한다.
    for m in re.finditer(r'\{\s*"headline"', s):
        for cand in reversed(_scan(s, m.start())):
            if (d := _ok(cand)):
                return d
    return None


RULES = """규칙:
- 전부 한국어. 지수명·티커·통화기호는 원문 유지.
- 확인되지 않은 수치는 지어내지 말고 그 항목을 통째로 빼세요.
- 매수·매도 판단, 목표가, 투자 권고를 절대 쓰지 마세요. 관측된 사실과 배경만 전달합니다.
- 커피가 월평균값이면 "월평균"이라고 명시하세요.
- 톤: 관찰하고 건넨다. 응원하거나 하루를 평가하지 않습니다."""

MARKET = json.dumps(market, ensure_ascii=False, indent=2)


def call(prompt, max_tokens, tools=None, label=""):
    """pause_turn을 처리하며 텍스트를 모은다. (텍스트, 마지막 stop_reason) 반환."""
    messages = [{"role": "user", "content": prompt}]
    turns, stop = [], None
    for n in range(6):
        kw = dict(model="claude-sonnet-5", max_tokens=max_tokens, messages=messages)
        if tools:
            kw["tools"] = tools
        resp = client.messages.create(**kw)
        stop = resp.stop_reason
        turns.append("".join(b.text for b in resp.content if b.type == "text"))
        print(f"  {label} 턴 {n+1}: stop_reason={stop}", flush=True)
        if stop != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    return ("\n".join(turns), stop)


def fallback():
    items = []
    for v in market.get("items", {}).values():
        cp = v.get("change_pct")
        items.append({
            "label": v.get("label", ""),
            "value": f"{v.get('price', '')}",
            "change": f"{cp:+.2f}%" if isinstance(cp, (int, float)) else "",
            "dir": "flat" if not isinstance(cp, (int, float))
                   else ("up" if cp > 0 else "down" if cp < 0 else "flat"),
            "body": v.get("note", ""),
        })
    return {"headline": "자동 요약을 만들지 못해 수집된 수치만 표시합니다.",
            "note": "해설 생성이 실패했습니다. Actions 로그를 확인하세요.",
            "items": items}


brief, notes = None, ""
try:
    # ── 1단계: 검색으로 빠진 수치와 배경만 수집한다 (JSON을 만들지 않는다) ──
    # 검색 결과가 응답 토큰을 잡아먹어 JSON 작성 중 max_tokens로 잘리는 것을 막기 위해 분리했다.
    notes, _ = call(
        f"""오늘은 {date_ko}(KST)입니다. 한국 개인 투자자용 아침 시장 브리핑에 쓸 자료를 조사하세요.

이미 확보한 수치입니다 (이 숫자는 정확하니 다시 찾지 마세요):
{MARKET}

`missing`에 있는 항목만 웹 검색으로 어제자 수치를 찾으세요.
그리고 나스닥·S&P500·유가·환율·금·커피가 어제 왜 그렇게 움직였는지 배경을 확인하세요.

결과를 짧은 메모 형식으로 정리하세요. 항목당 두 줄을 넘기지 마세요.
JSON으로 만들지 말고 평문 메모로만 쓰세요.""",
        max_tokens=6000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        label="조사")

    # ── 2단계: 검색 없이 JSON만 작성한다. 토큰 예산을 온전히 쓴다. ──
    text, stop = call(
        f"""아래 자료로 한국어 아침 시장 브리핑을 만드세요.

확정 수치 (그대로 사용):
{MARKET}

조사 메모:
{notes[:6000]}

{RULES}

다룰 항목: 나스닥 종합, 나스닥 100, S&P 500, 금, WTI, 브렌트유, 원/달러, 아라비카 커피.
자료에 없는 항목은 빼세요.

답변은 ```json 코드펜스 하나로만 감싸고 그 밖에는 아무것도 쓰지 마세요.
문자열 안에 큰따옴표를 쓰지 말고 필요하면 작은따옴표를 쓰세요.
각 body는 두 문장 이내로 짧게 쓰세요.
{{
  "headline": "오늘 시장을 한 문장으로",
  "items": [
    {{"label": "나스닥 종합", "value": "24,442.94", "change": "-1.74%", "dir": "down",
      "body": "왜 그렇게 움직였는지 한두 문장"}}
  ],
  "note": "전반을 관통하는 맥락 한두 문장. 없으면 빈 문자열"
}}""",
        max_tokens=8000, label="작성")

    if stop == "max_tokens":
        print("  ! 작성이 max_tokens로 잘렸습니다", flush=True)
    brief = extract_json(text)
except Exception as ex:
    print(f"! API 호출 실패: {type(ex).__name__}: {ex}", flush=True)
    text = ""

if brief:
    print(f"  파싱 성공 — 항목 {len(brief.get('items', []))}개", flush=True)
else:
    pathlib.Path("raw_response.txt").write_text(
        f"=== 조사 ===\n{notes}\n\n=== 작성 ===\n{locals().get('text','')}", encoding="utf-8")
    print("! JSON 파싱 실패 — 수집된 수치만으로 렌더링합니다.\n"
          f"--- 작성 응답 앞부분 ---\n{locals().get('text','')[:1200]}", flush=True)
    brief = fallback()

e = html.escape
ARROW = {"up": "▲", "down": "▼", "flat": "―"}
COLOR = {"up": "#C6613F", "down": "#2F6F8F", "flat": "#6B6A63"}

rows = "".join(
    f'''<div class="row">
<div class="rh"><span class="lbl">{e(str(it.get("label","")))}</span>
<span class="val">{e(str(it.get("value","")))}</span>
<span class="chg" style="color:{COLOR.get(it.get("dir","flat"),"#6B6A63")}">{ARROW.get(it.get("dir","flat"),"")} {e(str(it.get("change","")))}</span></div>
<p class="body">{e(str(it.get("body","")))}</p></div>'''
    for it in brief.get("items", [])
)

note = f'<p class="note">{e(brief.get("note",""))}</p>' if brief.get("note") else ""

page = f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>모닝 브리핑 · {e(date_ko)}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#FCFCFB;color:#2E2C27;font-family:-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:720px;margin:0 auto;padding:56px 24px 72px}}
.date{{font-size:13px;color:#6B6A63;margin:0 0 14px}}
h1{{font-family:"AppleMyungjo","Nanum Myeongjo","Batang",serif;font-weight:600;font-size:33px;line-height:1.45;margin:0 0 8px;word-break:keep-all;letter-spacing:-.015em}}
.note{{font-size:14.5px;line-height:1.85;color:#6B6A63;margin:0 0 40px;word-break:keep-all}}
.row{{padding:22px 0;border-top:1px solid #E4E3DC}}
.rh{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 7px}}
.lbl{{font-size:15px;font-weight:600}}
.val{{font-size:15px;font-variant-numeric:tabular-nums}}
.chg{{font-size:13.5px;font-variant-numeric:tabular-nums}}
.body{{font-size:14px;line-height:1.85;color:#6B6A63;margin:0;word-break:keep-all}}
footer{{margin-top:44px;padding-top:20px;border-top:1px solid #E4E3DC;font-size:12.5px;line-height:1.8;color:#B4B3A8}}
a{{color:#6B6A63}}
@media(max-width:640px){{h1{{font-size:26px}}.wrap{{padding:36px 20px 56px}}}}
</style></head><body><div class="wrap">
<p class="date">{e(date_ko)} · KST</p>
<h1>{e(brief.get("headline",""))}</h1>
{note}
{rows}
<footer>자동 생성된 시장 요약입니다. 투자 자문이 아니며, 매매 판단의 근거로 삼기 전에 원출처를 확인하세요.<br>
생성 {e(market.get("generated_at",""))} · <a href="./">지난 브리핑</a></footer>
</div></body></html>'''

(docs / f"{date_iso}.html").write_text(page, encoding="utf-8")

# 아카이브 인덱스
files = sorted([p.name for p in docs.glob("2*.html")], reverse=True)
links = "".join(f'<li><a href="./{e(f)}">{e(f[:-5])}</a></li>' for f in files)
(docs / "index.html").write_text(f'''<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>모닝 브리핑</title>
<style>body{{margin:0;background:#FCFCFB;color:#2E2C27;font-family:-apple-system,"Apple SD Gothic Neo",sans-serif}}
.wrap{{max-width:720px;margin:0 auto;padding:56px 24px}}
h1{{font-family:"AppleMyungjo","Nanum Myeongjo",serif;font-weight:600;font-size:30px;margin:0 0 28px}}
ul{{list-style:none;padding:0;margin:0}}li{{padding:12px 0;border-top:1px solid #E4E3DC}}
a{{color:#2E2C27;text-decoration:none}}a:hover{{text-decoration:underline}}</style></head>
<body><div class="wrap"><h1>모닝 브리핑</h1><ul>{links}</ul></div></body></html>''', encoding="utf-8")

print(f"완료 → docs/{date_iso}.html (총 {len(files)}건)")
