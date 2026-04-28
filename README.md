# 국내 주식 자동매매 시스템

키움증권 REST API를 활용한 실거래 가능한 자동매매 엔진. 전략·리스크·주문 모듈을 분리한 확장 가능한 아키텍처.

## 주요 기능

- 키움증권 REST API 연동 — 실시간 시세 조회 및 주문 실행
- 전략(strategy) · 리스크 모니터(monitor) · 주문 모듈 분리 설계
- `ORDER_EXECUTION_ENABLED=false` 안전장치로 페이퍼 트레이딩 검증
- Next.js 실시간 포트폴리오 모니터링 대시보드

## 기술 스택

| 구분 | 기술 |
|---|---|
| 백엔드 | Python · FastAPI · PostgreSQL · Redis |
| 프론트엔드 | Next.js |
| 인프라 | Docker · Docker Compose |
| 데이터 | 키움증권 REST API |

## 실행 방법

```bash
# 전체 스택 실행 (페이퍼 트레이딩 모드)
docker-compose up

# 실거래 활성화 시 (주의)
# docker-compose.yml에서 ORDER_EXECUTION_ENABLED=true 설정
```

## 아키텍처

```
trading_engine_project/
├── backend/          # FastAPI 서버, 전략·리스크·주문 모듈
├── frontend/         # Next.js 대시보드
├── docs/             # 설계 문서
└── docker-compose.yml
```
