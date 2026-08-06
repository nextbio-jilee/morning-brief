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

PROMPT = f"""오늘은 {date_ko}(KST)입니다. 한국의 개인 투자자를 위한 아침 시장 브리핑을 작성하세요.

아래는 API로 확보한 확정 수치입니다. 이 숫자는 그대로 쓰고 절대 바꾸지 마세요.

{json.dumps(market, ensure_ascii=False, indent=2)}

`missing` 목록에 있는 항목은 API로 못 받은 것입니다. 웹 검색으로 어제자 수치를 찾아 채우세요.
각 항목이 왜 그렇게 움직였는지 배경도 웹 검색으로 확인하세요.

다룰 항목: 나스닥 종합·나스닥 100, S&P 500, 금, WTI·브렌트유, 원/달러, 아라비카 커피.

규칙:
- 전부 한국어. 지수명·티커·통화기호는 원문 유지.
- 확인되지 않은 수치는 지어내지 말고 그 항목을 통째로 빼세요. 사과나 자리표시자를 남기지 마세요.
- 매수·매도 판단, 목표가, 투자 권고를 절대 쓰지 마세요. 관측된 사실과 배경만 전달합니다.
- 커피가 월평균값이면 "월평균"이라고 명시하세요.
- 톤: 관찰하고 건넨다. 응원하거나 하루를 평가하지 않습니다.

아래 JSON 형식으로만 답하세요. 다른 텍스트는 넣지 마세요.
{{
  "headline": "오늘 시장을 한 문장으로. 명조체로 크게 나갈 문장입니다.",
  "items": [
    {{"label": "나스닥 종합", "value": "24,442.94", "change": "-1.74%", "dir": "down",
      "body": "왜 그렇게 움직였는지 한두 문장."}}
  ],
  "note": "전반을 관통하는 맥락 한두 문장. 없으면 빈 문자열."
}}
"""

# 서버측 웹 검색을 쓰면 API가 stop_reason="pause_turn"으로 턴을 끊는다.
# 단발 호출만 하면 최종 텍스트가 비어 실패하므로, 끝날 때까지 이어서 호출한다.
messages = [{"role": "user", "content": PROMPT}]
chunks, stop, resp = [], None, None

for turn in range(6):
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=8000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        messages=messages,
    )
    stop = resp.stop_reason
    chunks += [b.text for b in resp.content if b.type == "text"]
    print(f"  턴 {turn + 1}: stop_reason={stop}, 블록 {len(resp.content)}개", flush=True)
    if stop != "pause_turn":
        break
    messages.append({"role": "assistant", "content": resp.content})

text = "\n".join(chunks)
m = re.search(r"\{.*\}", text, re.S)

if m:
    brief = json.loads(m.group(0))
else:
    # 모델 응답을 못 쓰더라도 원시 수치는 보여준다. 빌드를 실패시키지 않는다.
    print(f"! 모델이 JSON을 반환하지 않았습니다 (stop_reason={stop}). "
          f"수집된 수치만으로 렌더링합니다.\n--- 응답 앞부분 ---\n{text[:600]}", flush=True)
    items = []
    for v in market.get("items", {}).values():
        cp = v.get("change_pct")
        items.append({
            "label": v.get("label", ""),
            "value": f"{v.get('price', '')}",
            "change": f"{cp:+.2f}%" if isinstance(cp, (int, float)) else "",
            "dir": "flat" if not isinstance(cp, (int, float)) else ("up" if cp > 0 else "down" if cp < 0 else "flat"),
            "body": v.get("note", ""),
        })
    brief = {"headline": "자동 요약을 만들지 못해 수집된 수치만 표시합니다.",
             "note": "해설 생성이 실패했습니다. Actions 로그를 확인하세요.",
             "items": items}

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
