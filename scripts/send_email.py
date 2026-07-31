"""선택 사항 — 오늘 브리핑을 구독자에게 발송. SUBSCRIBERS는 쉼표로 구분한 이메일 목록."""
import os, json, datetime, pathlib, urllib.request

KST = datetime.timezone(datetime.timedelta(hours=9))
date_iso = datetime.datetime.now(KST).strftime("%Y-%m-%d")
path = pathlib.Path("docs") / f"{date_iso}.html"
if not path.exists():
    print(f"{path} 없음 — 발송 건너뜀"); raise SystemExit(0)

if not os.environ.get("RESEND_API_KEY"):
    print("RESEND_API_KEY 없음 — 이메일 발송 비활성"); raise SystemExit(0)

to = [a.strip() for a in os.environ.get("SUBSCRIBERS", "").split(",") if a.strip()]
if not to:
    print("SUBSCRIBERS 비어 있음 — 발송 건너뜀"); raise SystemExit(0)

body = json.dumps({
    "from": os.environ.get("FROM_ADDRESS", "brief@example.com"),
    "to": to,
    "subject": f"모닝 브리핑 · {date_iso}",
    "html": path.read_text(encoding="utf-8"),
}).encode()

req = urllib.request.Request(
    "https://api.resend.com/emails", data=body, method="POST",
    headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}",
             "Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=30) as r:
    print(f"발송 완료 ({len(to)}명):", r.read().decode()[:200])
