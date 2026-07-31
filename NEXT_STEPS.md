# 다음에 할 일

7월 31일 기준. 코드 업로드까지 완료, 설정 3단계가 남았습니다.

## 남은 것 — 전부 GitHub 웹사이트에서, 터미널 불필요

### 1. API 키 3개 발급

Claude에 연결한 커넥터와는 **별개**입니다. 커넥터는 로그인 방식이라 원본 키를 주지 않습니다.

- [ ] `ANTHROPIC_API_KEY` — console.anthropic.com → API Keys → Create Key
      (Claude 구독과 별개로 결제 수단 등록 필요. 월 1달러 안팎)
- [ ] `FMP_KEY` — financialmodelingprep.com → Dashboard
- [ ] `ALPHAVANTAGE_KEY` — alphavantage.co/support/#api-key (이메일만 넣으면 즉시)

### 2. Secrets 등록

Settings → Secrets and variables → Actions → New repository secret

이름을 위 표기 그대로 (대문자, 밑줄) 세 번 반복.

### 3. Pages 켜기

Settings → Pages → Source `Deploy from a branch` → `main` / `/docs` → Save

**Private 저장소면 Pages가 유료입니다.** 무료 계정이면 Public으로 전환.
Secrets는 Public에서도 안전합니다 — 암호화 저장되고 포크한 사람에게 가지 않습니다.

### 4. 첫 실행

Actions 탭 → 모닝 브리핑 → Run workflow

빨간 X가 뜨면 실패한 단계의 로그를 펼쳐 확인. 첫 실행 실패는 흔하고,
대부분 키 오타이거나 API 플랜 제한입니다.

---

## 별개로 남은 것

- [ ] **Finnhub 키** — `echo "키" > ~/Documents/finnhub.key`
      로컬 예약작업이 이 파일을 자동으로 찾습니다. SKILL.md는 건드릴 필요 없습니다.

- [ ] **Google 캘린더 시간대** — 현재 UTC로 설정되어 있음
      calendar.google.com → 설정 → 일반 → 시간대 → `(GMT+09:00) 서울`
      계정: beltigerlee2@gmail.com

- [ ] **Pages 주소 확정 후** — Tweek 할 일 note에 링크를 넣도록 예약작업 수정
      (주소가 생기면 "클릭해서 타고 들어가기"가 그때부터 가능해짐)

- [ ] `~/morning-brief-kr` 폴더 정리 — 예전에 복사해둔 것으로 이제 불필요.
      원본은 `~/Claude/Scheduled/morning-brief-kr/`에 따로 있으니 지워도 무방.

---

## 이미 돌아가고 있는 것

- **로컬 예약작업** — 평일 07:00 KST, 캘린더 + 개인 Gmail + 시장 + Tweek 등록.
  7월 31일 아침 정상 실행 확인. 단 Mac이 켜져 있어야 함.

- **GitHub Actions** — 위 설정 완료 시 평일 07:00 KST 자동 실행. PC 무관.

---

## 알려진 제약

- FMP의 `commodity`·`forex`·`quote`는 상위 플랜 전용이라 막혀 있음
- Alpha Vantage 커피는 월간 데이터만, 최신값이 1~2개월 뒤처짐
- 그래서 금·커피 일간 시세는 웹 검색으로 채우는 구조
- GitHub 예약 실행은 서버 상황에 따라 5~20분 지연될 수 있음
- 60일간 커밋이 없으면 GitHub이 예약 실행을 자동 중단 (Actions 탭에서 재활성화)
