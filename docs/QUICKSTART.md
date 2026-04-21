# 실전 투자 운영 앱 — macOS 로컬 실행 가이드

## 전제 조건

```bash
# macOS에서 필요한 것만
brew install docker        # Docker Desktop for Mac 또는 OrbStack
brew install node          # Node.js 20+
brew install python@3.12
```

---

## 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 열어서 반드시 입력:
```
KIWOOM_APP_KEY=발급받은키
KIWOOM_APP_SECRET=발급받은시크릿
KIWOOM_ACCOUNT_NUMBER=계좌번호10자리
ORDER_EXECUTION_ENABLED=false   # 처음엔 반드시 false
```

Kiwoom REST API 키 발급: openapi.kiwoom.com > 로그인 > 앱 등록

---

## 2. Docker로 전체 실행 (권장)

```bash
cd /Users/snu/trading_engine_project
docker compose up --build
```

- 백엔드: http://localhost:8000
- 프론트엔드: http://localhost:3000
- API 문서: http://localhost:8000/docs

---

## 3. 로컬 개발 (Docker 없이)

### PostgreSQL + Redis 만 Docker로

```bash
docker compose up postgres redis -d
```

### 백엔드

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 환경변수 로드
cp ../.env.example .env  # 또는 상위의 .env 링크

# 실행
uvicorn app.main:app --reload --port 8000
```

### 초기 데이터 시드 (테마 + 종목 universe)

```bash
cd backend
python seed_themes.py
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

---

## 4. iPhone/iPad에서 접속

같은 WiFi 내에서 접속:

```bash
# macOS IP 확인
ipconfig getifaddr en0

# 예: 192.168.1.100
# iPhone Safari에서 http://192.168.1.100:3000 접속
```

홈 화면에 추가 (PWA):
Safari > 공유 버튼 > 홈 화면에 추가

---

## 5. Kiwoom API 키 발급 절차

1. openapi.kiwoom.com 접속
2. 회원가입 / 로그인 (키움증권 계좌 필요)
3. 앱 등록 → App Key / Secret Key 발급
4. IP 등록 (사용할 서버/맥 IP 등록 필수)
5. .env에 입력

---

## 6. 실주문 활성화 절차

⚠ 이 절차를 완료하면 실전 계좌에 실주문이 전송됩니다.

1. openapi.kiwoom.com에서 실전 계좌 권한 확인
2. .env에서 `ORDER_EXECUTION_ENABLED=true` 로 변경
3. 서버 재시작
4. 주문 화면에서 "1차 확인" → "실주문 확정" 두 단계 필요
5. 최종 팝업에서 "EXECUTE" 확인

---

## 7. Kiwoom REST API 제한사항

### macOS에서 가능 ✅
- OAuth2 토큰 발급
- 계좌/잔고/포지션 조회
- 현재가/호가 조회
- 주식 매수/매도 주문
- 주문 상태 조회/취소
- WebSocket 실시간 시세

### macOS에서 불가능 ❌
- OpenAPI+ (COM/OCX 기반) — Windows 전용
- KOA Studio (Windows 전용 GUI 도구)
- 조건검색 트리거 (OCX 이벤트 기반 일부 기능)

### 우회 방법
- 조건검색: REST API의 조건검색 WebSocket 엔드포인트 사용
- 실시간 체결/잔고 변경 알림: WebSocket `wss://api.kiwoom.com:10000`
- 완전한 OCX 기능 필요 시: 별도 Windows 서버 + 브리지 API 구성

---

## 8. API 엔드포인트 확인 필요 항목

kiwoom.py의 아래 경로는 **openapi.kiwoom.com > API 가이드** 에서 반드시 확인 후 수정:

| 기능 | 현재 추정 경로 | 확인 필요 |
|------|-------------|---------|
| 토큰 발급 | `/oauth2/token` | au10001 |
| 계좌 잔고 | `/api/dostk/acnt` | kt00018 등 |
| 현재가 | `/api/dostk/stkinfo` | ka10001 등 |
| 주문 | `/api/dostk/ordr` | kt10000 등 |
| 주문 취소 | `/api/dostk/ordr/cancel` | 확인 필요 |

---

## 9. 이후 확장 TODO

- [ ] Kiwoom WebSocket 실시간 시세 연동
- [ ] 뉴스 API 연동 (news_score 실제 계산)
- [ ] 배당 일정 크롤링 / 저장
- [ ] 급락 자동 알림 (APNs / 텔레그램)
- [ ] 종목 재무 데이터 주기적 갱신
- [ ] 포트폴리오 차트 (월별 수익률 그래프)
- [ ] 추천 엔진 가중치 A/B 테스트
- [ ] 실주문 체결 결과 WebSocket 실시간 수신
