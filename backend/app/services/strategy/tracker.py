"""
전략 성과 추적 & 회고 시스템.

흐름:
  추천 생성 → was_executed 플래그 → Trade 기록 → PerformanceRecord 업데이트
  → 주기적 성과 집계 → 전략 규칙 개선
"""

from __future__ import annotations
from datetime import datetime, date
from typing import Any
import structlog

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.strategy import (
    Recommendation, RecommendationItem, Trade, PerformanceRecord, StrategyRule
)
from app.models.stock import Stock

logger = structlog.get_logger()


class StrategyTracker:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_recommendation(
        self,
        top_themes: list[str],
        items: list[dict],
        rule_version: str = "v1",
        market_note: str | None = None,
        strategy_number: int = 1,
    ) -> Recommendation:
        """추천 결과를 DB에 저장."""
        rec = Recommendation(
            run_at=datetime.utcnow(),
            rule_version=rule_version,
            top_themes=top_themes,
            market_note=market_note,
            strategy_number=strategy_number,
        )
        self._db.add(rec)
        await self._db.flush()

        for item in items:
            ri = RecommendationItem(
                recommendation_id=rec.id,
                stock_id=item["stock_id"],
                theme_id=item.get("theme_id"),
                action=item["action"],
                priority=item.get("priority", 5),
                theme_score=item.get("theme_score"),
                stock_score=item.get("stock_score"),
                score_detail=item.get("detail"),
                reason=item.get("reason"),
                target_price=item.get("target_price"),
                stop_loss=item.get("stop_loss"),
                price_at_recommendation=item.get("current_price"),
            )
            self._db.add(ri)

        await self._db.commit()
        logger.info("recommendation_saved", rec_id=rec.id, item_count=len(items))
        return rec

    async def record_trade(
        self,
        stock_id: int,
        action: str,
        quantity: int,
        price: float,
        traded_at: datetime,
        order_item_id: int | None = None,
        recommendation_item_id: int | None = None,
        broker_order_id: str | None = None,
        note: str | None = None,
    ) -> Trade:
        """실제 체결 기록 저장."""
        fee = price * quantity * 0.00015   # 키움 수수료 약 0.015%
        tax = (price * quantity * 0.0020) if action == "sell" else 0.0  # 증권거래세

        trade = Trade(
            stock_id=stock_id,
            order_item_id=order_item_id,
            recommendation_item_id=recommendation_item_id,
            action=action,
            quantity=quantity,
            price=price,
            amount=price * quantity,
            fee=round(fee, 0),
            tax=round(tax, 0),
            broker_order_id=broker_order_id,
            traded_at=traded_at,
            note=note,
        )
        self._db.add(trade)

        # RecommendationItem was_executed 업데이트
        if recommendation_item_id:
            result = await self._db.execute(
                select(RecommendationItem).where(
                    RecommendationItem.id == recommendation_item_id
                )
            )
            ri = result.scalar_one_or_none()
            if ri:
                ri.was_executed = True

        await self._db.commit()
        logger.info("trade_recorded", stock_id=stock_id, action=action, price=price)
        return trade

    async def update_performance(
        self,
        recommendation_item_id: int,
        exit_price: float | None = None,
        exit_date: date | None = None,
        max_gain_pct: float | None = None,
        max_loss_pct: float | None = None,
        post_review: str | None = None,
    ) -> PerformanceRecord:
        """성과 기록 업데이트."""
        result = await self._db.execute(
            select(PerformanceRecord).where(
                PerformanceRecord.recommendation_item_id == recommendation_item_id
            )
        )
        perf = result.scalar_one_or_none()

        if perf is None:
            ri_result = await self._db.execute(
                select(RecommendationItem).where(
                    RecommendationItem.id == recommendation_item_id
                )
            )
            ri = ri_result.scalar_one()
            perf = PerformanceRecord(
                recommendation_item_id=recommendation_item_id,
                stock_id=ri.stock_id,
                entry_price=ri.price_at_recommendation,
                score_at_recommendation=ri.stock_score,
                rule_version=ri.recommendation.rule_version if ri.recommendation else "v1",
            )
            self._db.add(perf)

        if exit_price is not None:
            perf.exit_price = exit_price
            perf.exit_date = exit_date or date.today()
            if perf.entry_price and perf.entry_price > 0:
                perf.realized_pnl = (exit_price - perf.entry_price) * (perf.exit_quantity or 1)
                perf.realized_pnl_pct = (
                    (exit_price - perf.entry_price) / perf.entry_price * 100
                )
            if perf.entry_date:
                perf.holding_days = (perf.exit_date - perf.entry_date).days
            perf.is_closed = True

        if max_gain_pct is not None:
            perf.max_gain_pct = max_gain_pct
        if max_loss_pct is not None:
            perf.max_loss_pct = max_loss_pct
        if post_review is not None:
            perf.post_review = post_review

        await self._db.commit()
        return perf

    async def get_stats(self) -> dict[str, Any]:
        """전략 성과 집계."""
        result = await self._db.execute(
            select(PerformanceRecord).where(PerformanceRecord.is_closed == True)
        )
        closed = result.scalars().all()

        if not closed:
            return {"total_trades": 0, "message": "아직 종료된 포지션이 없습니다"}

        total = len(closed)
        wins = [p for p in closed if (p.realized_pnl_pct or 0) > 0]
        win_rate = len(wins) / total * 100
        avg_return = sum(p.realized_pnl_pct or 0 for p in closed) / total
        avg_holding = sum(p.holding_days or 0 for p in closed) / total

        sorted_by_return = sorted(closed, key=lambda p: p.realized_pnl_pct or 0)

        # 버전별 집계
        by_version: dict[str, list] = {}
        for p in closed:
            v = p.rule_version or "v1"
            by_version.setdefault(v, []).append(p.realized_pnl_pct or 0)

        version_stats = [
            {
                "version": v,
                "count": len(returns),
                "avg_return_pct": round(sum(returns) / len(returns), 2),
                "win_rate": round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1),
            }
            for v, returns in by_version.items()
        ]

        return {
            "total_trades": total,
            "win_rate": round(win_rate, 1),
            "avg_return_pct": round(avg_return, 2),
            "avg_holding_days": round(avg_holding, 1),
            "best_pnl_pct": sorted_by_return[-1].realized_pnl_pct if closed else None,
            "worst_pnl_pct": sorted_by_return[0].realized_pnl_pct if closed else None,
            "by_rule_version": version_stats,
        }

    async def activate_strategy_rule(
        self, version: str, parameters: dict, description: str | None = None
    ) -> StrategyRule:
        """전략 규칙 버전 활성화 (이전 버전 비활성화)."""
        # 기존 활성 규칙 비활성화
        result = await self._db.execute(
            select(StrategyRule).where(StrategyRule.is_active == True)
        )
        for old in result.scalars().all():
            old.is_active = False

        new_rule = StrategyRule(
            version=version,
            is_active=True,
            description=description,
            parameters=parameters,
            activated_at=datetime.utcnow(),
        )
        self._db.add(new_rule)
        await self._db.commit()
        logger.info("strategy_rule_activated", version=version)
        return new_rule
