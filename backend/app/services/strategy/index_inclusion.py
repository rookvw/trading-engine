"""
전략2: 지수 편입 이벤트 드리븐 전략.

로직:
  1. index_inclusion_events 테이블에서 status='announced' 이벤트 조회
  2. 현재일 >= announcement_date 이고 현재일 < inclusion_date 인 종목
     → 강제 매수 신호 생성
  3. inclusion_date 도달 → status='included' 업데이트
  4. 편입 후 보유유지 or 익절 판단은 전략1과 동일한 성과 추적 구조 활용

왜 이 전략이 작동하는가:
  - 지수 편입 확정 시 패시브 펀드(ETF, 인덱스 펀드)가 의무 매수
  - 발표일 ~ 편입일 사이 수급 압력으로 가격 상승 경향
  - 단, 이미 발표 전 프리어닝이 반영된 경우 역전 가능 → 진입 타이밍 중요

지원 지수:
  - SP500    : S&P 다우존스 인덱스 발표 (미국 주식 → 향후 해외주식 연동 시 활용)
  - KOSPI200 : 한국거래소 반기 리뷰 (6월/12월 발표)
  - MSCI     : MSCI 분기 리뷰

현재 MVP 범위:
  - 이벤트는 수동 입력 (API/크롤링은 TODO)
  - 신호 생성 → recommendation_items로 연결
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Any
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.strategy import IndexInclusionEvent, Recommendation, RecommendationItem
from app.models.stock import Stock
from app.services.broker.base import BrokerBase

logger = structlog.get_logger()


class IndexInclusionStrategy:
    def __init__(self, db: AsyncSession, broker: BrokerBase) -> None:
        self._db = db
        self._broker = broker

    async def run(self, rule_version: str = "v2") -> Recommendation:
        """
        활성 편입 이벤트 스캔 → 매수 신호 생성 → Recommendation 저장.
        """
        today = date.today()

        # 매수 신호 대상: 발표됐고 아직 편입 확정일 전인 이벤트
        result = await self._db.execute(
            select(IndexInclusionEvent).where(
                and_(
                    IndexInclusionEvent.status == "announced",
                    IndexInclusionEvent.announcement_date <= today,
                    IndexInclusionEvent.inclusion_date > today,
                )
            )
        )
        events = result.scalars().all()

        # 편입 확정일 지난 이벤트 상태 업데이트
        await self._update_expired_events(today)

        items = []
        for event in events:
            item = await self._build_signal(event)
            if item:
                items.append(item)
                event.signal_generated = True
                event.recommended_at = datetime.utcnow()

        rec = Recommendation(
            run_at=datetime.utcnow(),
            rule_version=rule_version,
            strategy_type="index_inclusion",
            top_themes=[e.index_name for e in events],
            market_note=f"편입 이벤트 {len(events)}건 활성",
        )
        self._db.add(rec)
        await self._db.flush()

        for item_data in items:
            ri = RecommendationItem(
                recommendation_id=rec.id,
                stock_id=item_data["stock_id"],
                action="new_entry",
                priority=1,  # 강제 매수 → 최우선순위
                theme_score=1.0,
                stock_score=item_data["stock_score"],
                score_detail=item_data["detail"],
                reason=item_data["reason"],
                price_at_recommendation=item_data.get("current_price"),
            )
            self._db.add(ri)

        await self._db.commit()
        logger.info(
            "index_inclusion_strategy_run",
            events=len(events),
            signals=len(items),
        )
        return rec

    async def _build_signal(self, event: IndexInclusionEvent) -> dict[str, Any] | None:
        """편입 이벤트 → 매수 신호 데이터 생성."""
        # DB에서 종목 조회 (없으면 자동 생성)
        result = await self._db.execute(
            select(Stock).where(Stock.symbol == event.symbol)
        )
        stock = result.scalar_one_or_none()

        if stock is None:
            stock = Stock(
                symbol=event.symbol,
                name=event.stock_name,
                market=event.market,
                stock_type="theme",
            )
            self._db.add(stock)
            await self._db.flush()

        today = date.today()
        days_to_inclusion = (event.inclusion_date - today).days

        # 현재가 조회 시도
        current_price = None
        try:
            quote = await self._broker.get_quote(event.symbol)
            current_price = quote.current_price
        except Exception:
            pass  # 시세 없어도 신호는 생성

        # 편입일 임박할수록 긴급도 높음
        urgency_score = max(0.5, 1.0 - days_to_inclusion / 30)

        reason = (
            f"{event.index_name} 편입 확정 "
            f"(발표: {event.announcement_date}, 편입일: {event.inclusion_date}, "
            f"D-{days_to_inclusion}). "
            f"패시브 펀드 의무 매수 수급 예상. "
        )
        if event.source_note:
            reason += event.source_note

        return {
            "stock_id": stock.id,
            "stock_score": round(urgency_score, 4),
            "current_price": current_price,
            "reason": reason,
            "detail": {
                "index_name": event.index_name,
                "announcement_date": str(event.announcement_date),
                "inclusion_date": str(event.inclusion_date),
                "days_to_inclusion": days_to_inclusion,
                "urgency_score": urgency_score,
                "market": event.market,
            },
        }

    async def _update_expired_events(self, today: date) -> None:
        """편입 확정일 지난 이벤트 → status='included'로 업데이트."""
        result = await self._db.execute(
            select(IndexInclusionEvent).where(
                and_(
                    IndexInclusionEvent.status == "announced",
                    IndexInclusionEvent.inclusion_date <= today,
                )
            )
        )
        for event in result.scalars().all():
            event.status = "included"
            logger.info(
                "index_inclusion_completed",
                symbol=event.symbol,
                index=event.index_name,
            )
        await self._db.commit()

    # ─────────────────────────────────────────
    # 이벤트 관리 (수동 입력 MVP)
    # ─────────────────────────────────────────

    async def add_event(
        self,
        index_name: str,
        symbol: str,
        stock_name: str,
        market: str,
        announcement_date: date,
        inclusion_date: date,
        removal_symbol: str | None = None,
        source_note: str | None = None,
    ) -> IndexInclusionEvent:
        """편입 이벤트 수동 등록."""
        event = IndexInclusionEvent(
            index_name=index_name,
            symbol=symbol,
            stock_name=stock_name,
            market=market,
            announcement_date=announcement_date,
            inclusion_date=inclusion_date,
            removal_symbol=removal_symbol,
            source_note=source_note,
            status="announced",
        )
        self._db.add(event)
        await self._db.commit()
        logger.info(
            "index_inclusion_event_added",
            index=index_name,
            symbol=symbol,
            inclusion_date=str(inclusion_date),
        )
        return event

    async def cancel_event(self, event_id: int, reason: str | None = None) -> None:
        """이벤트 취소 (편입 철회 시)."""
        result = await self._db.execute(
            select(IndexInclusionEvent).where(IndexInclusionEvent.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event.status = "cancelled"
            if reason:
                event.source_note = (event.source_note or "") + f" [취소: {reason}]"
            await self._db.commit()
