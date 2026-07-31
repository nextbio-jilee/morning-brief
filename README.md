# 모닝 브리핑 — GitHub Actions 자동 실행

평일 07:00(KST)에 GitHub 서버에서 자동 실행됩니다. **PC가 꺼져 있어도 돌아갑니다.**
결과는 GitHub Pages에 웹페이지로 올라가고, 원하면 이메일로도 발송됩니다.

---

## 먼저 알아야 할 것 — 무엇이 옮겨지고 무엇이 안 옮겨지는가

| 항목 | GitHub에서 | 이유 |
|---|---|---|
| 지수·환율·유가·금·커피 | **작동** | API 키만 있으면 됨 |
| 시장 배경 뉴스 | **작동** | Claude API의 웹 검색 사용 |
| 웹페이지 발행 | **작동** | GitHub Pages |
| 이메일 발송 | **작동** | Resend (선택) |
| 개인 캘린더 일정 | **안 됨** | Google OAuth 토큰이 필요. 별도 작업 |
| 개인 Gmail | **안 됨** | 위와 동일 |
| Tweek 등록 | **안 됨** | OAuth 전용, 공개 API 없음 |

**그래서 두 개를 병행하는 구조가 됩니다.**

- **Mac의 예약 작업** — 캘린더 + 메일 + Tweek. PC가 켜져 있을 때만
- **GitHub Actions** — 시장 브리핑. 항상 작동, 남과 공유 가능

캘린더·메일까지 GitHub로 옮기려면 Google Cloud 프로젝트를 만들고 OAuth 리프레시 토큰을 발급받아야 합니다. 가능하지만 별개의 작업이고, 개인 메일 전체 접근 권한을 GitHub Secrets에 두게 되므로 권하지 않습니다.

---

## 설치 — 15분

### 1. 리포지토리 만들기

이 폴더 전체를 GitHub에 올립니다. **Private으로 만드세요** (Secrets 보호).

```bash
cd morning-brief
git init
git add .
git commit -m "최초 커밋"
git branch -M main
git remote add origin https://github.com/<본인계정>/morning-brief.git
git push -u origin main
```

### 2. API 키를 Secrets에 등록

리포지토리 → **Settings → Secrets and variables → Actions → New repository secret**

| 이름 | 어디서 받나 | 필수 |
|---|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys | **필수** |
| `FMP_KEY` | financialmodelingprep.com → Dashboard | **필수** (지수 담당) |
| `ALPHAVANTAGE_KEY` | alphavantage.co/support/#api-key | **필수** (환율·유가 담당) |
| `FINNHUB_KEY` | finnhub.io/dashboard | 선택 |
| `RESEND_API_KEY` | resend.com → API Keys | 이메일 발송 시에만 |
| `FROM_ADDRESS` | 예: `brief@본인도메인.com` | 이메일 발송 시에만 |
| `SUBSCRIBERS` | `a@x.com,b@y.com` (쉼표 구분) | 이메일 발송 시에만 |

**키는 화면에 붙여넣는 즉시 암호화되고 다시는 볼 수 없습니다.** 로그에도 `***`로 마스킹됩니다. 코드나 README에는 절대 적지 마세요.

### 3. GitHub Pages 켜기

**Settings → Pages** → Source를 `Deploy from a branch`, 브랜치 `main`, 폴더 `/docs` → Save.

1~2분 뒤 주소가 나옵니다:
```
https://<본인계정>.github.io/morning-brief/
```

> Private 리포지토리는 Pages가 유료 플랜에서만 됩니다. 무료로 웹 공개하려면 리포를 Public으로 바꾸되, **Secrets는 Public에서도 안전합니다** (별도 저장소에 암호화되며 포크한 사람에게 전달되지 않습니다).

### 4. 첫 실행

**Actions 탭 → 모닝 브리핑 → Run workflow.** 2~3분 걸립니다.
초록색 체크가 뜨면 `docs/2026-07-31.html`이 생기고 Pages 주소에서 열립니다.

---

## 다른 사람도 받아보게 하려면

### 방법 A — 주소만 알려주기 (가장 간단)

Pages 주소를 그대로 공유하면 끝입니다. 매일 아침 갱신됩니다.
카톡방에 링크 하나 던져두면 각자 알아서 봅니다.

### 방법 B — 이메일 발송

1. [resend.com](https://resend.com) 가입 (무료: 하루 100통)
2. 본인 도메인을 인증하거나, 테스트용 `onboarding@resend.dev` 사용
3. `RESEND_API_KEY`, `FROM_ADDRESS`, `SUBSCRIBERS`를 Secrets에 등록

`SUBSCRIBERS`에 쉼표로 주소를 나열하면 매일 아침 전원에게 갑니다.
사람이 늘고 줄면 Secret 값만 고치면 됩니다.

> 받는 사람이 원치 않을 때 스스로 빠질 방법이 없으므로, **동의를 받은 사람만** 넣으세요. 20명이 넘어가면 Resend Audiences나 메일침프처럼 수신거부가 되는 도구로 옮기는 게 맞습니다.

### 방법 C — 각자 자기 것을 갖게 하기

리포지토리를 Public으로 두면 다른 사람이 **Fork** 후 자기 API 키만 넣으면 됩니다.
브리핑 내용을 각자 취향대로 고칠 수 있습니다. 키는 공유되지 않습니다.

---

## 고치고 싶을 때

| 무엇 | 어디 |
|---|---|
| 실행 시각 | `.github/workflows/brief.yml`의 `cron` |
| 다루는 종목 | `scripts/fetch_market.py` 상단 심볼 목록 |
| 글의 톤·항목 | `scripts/generate.py`의 `PROMPT` |
| 디자인 | `scripts/generate.py` 하단 CSS |

**cron 주의:** GitHub Actions는 UTC로만 돕니다. `0 22 * * 0-4`는 UTC 일~목 22시 = **KST 월~금 07시**입니다. 시간을 바꿀 때 요일도 같이 계산하세요.

또 GitHub의 예약 실행은 서버가 붐비면 **5~20분 늦게** 시작할 수 있습니다. 정시 도착이 중요하면 06:40으로 당겨두세요.

---

## 비용

| | 무료 한도 | 이 작업의 사용량 |
|---|---|---|
| GitHub Actions | Public 무제한 / Private 월 2,000분 | 월 약 60분 |
| Anthropic API | 종량제 | 실행당 약 $0.02~0.05 (월 $1 내외) |
| Alpha Vantage | 일 25회 | 4회 |
| FMP | 플랜별 | 3회 |
| Resend | 일 100통 | 구독자 수만큼 |

---

## 안 될 때

**Actions가 안 돌아감** — 60일간 커밋이 없으면 GitHub가 예약 실행을 자동 중단합니다. Actions 탭에서 `Enable workflow`를 누르세요.

**`모델이 JSON을 반환하지 않았습니다`** — `ANTHROPIC_API_KEY` 오타이거나 크레딧 소진입니다. Actions 로그를 확인하세요.

**수치가 비어 있음** — `market.json`의 `missing` 배열을 보세요. API 플랜 제한일 수 있습니다. 현재 FMP 플랜에서는 `commodity`와 `forex`가 막혀 있어 금·커피 일간 시세는 웹 검색으로 채워집니다.

**Pages가 404** — 첫 배포는 최대 10분 걸립니다. Settings → Pages에서 초록 체크를 확인하세요.

---

## 면책

자동 생성된 시장 요약이며 투자 자문이 아닙니다. 수치는 무료 API에서 오고 지연되거나 틀릴 수 있습니다. 매매 판단 전에 반드시 원출처를 확인하세요.
