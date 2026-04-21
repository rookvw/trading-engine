from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.deps import get_db, get_broker_dep
from app.services.broker.base import BrokerBase
from app.services.recommendation import ThemeScorer, StockScorer
from app.services.strategy.tracker import StrategyTracker
from app.services.strategy.index_inclusion import IndexInclusionStrategy
from app.models.strategy import (
    Recommendation, RecommendationItem, PerformanceRecord, StrategyRule,
    IndexInclusionEvent,
)
from app.models.stock import Stock
from app.models.theme import Theme

router = APIRouter(prefix="/strategy", tags=["Strategy"])


@router.post("/recommend/run")
async def run_recommendation(
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """추천 엔진 즉시 실행 + 저장."""
    theme_scorer = ThemeScorer(db, broker)
    stock_scorer = StockScorer(db, broker)

    theme_scores = await theme_scorer.score_all_themes()
    await theme_scorer.persist_scores(theme_scores)

    stock_results = await stock_scorer.score_top_theme_stocks(
        theme_scores, top_n_themes=3, top_n_stocks=5
    )

    tracker = StrategyTracker(db)
    items = [
        {
            "stock_id": s.stock_id,
            "action": s.action,
            "priority": int((1.0 - s.combined_score) * 10),
            "theme_score": s.theme_score,
            "stock_score": s.stock_score,
            "reason": s.reason,
            "current_price": s.current_price,
            "sub_strategy": "active",
            "detail": {**s.detail, "cited_news": s.cited_news, "bucket": s.bucket},
        }
        for s in stock_results
    ]
    top_theme_codes = list(dict.fromkeys(s.theme_code for s in theme_scores[:3]))

    # VIX 시그널을 market_note에 포함
    vix_signal = theme_scores[0].vix_signal if theme_scores else "normal"
    market_note = f"VIX신호:{vix_signal}"
    if theme_scores and theme_scores[0].top_news:
        market_note += f" | 주요뉴스: {theme_scores[0].top_news[0]['title'][:60]}"

    rec = await tracker.save_recommendation(
        top_themes=top_theme_codes,
        items=items,
        market_note=market_note,
        strategy_number=1,
    )
    return {
        "recommendation_id": rec.id,
        "vix_signal": vix_signal,
        "top_themes": top_theme_codes,
        "item_count": len(items),
        "items": [
            {
                "symbol": s.symbol,
                "name": s.name,
                "action": s.action,
                "combined_score": s.combined_score,
                "reason": s.reason,
                "cited_news": s.cited_news,
                "current_price": s.current_price,
                "bucket": s.bucket,
            }
            for s in stock_results
        ],
    }


@router.get("/recommendations")
async def list_recommendations(
    limit: int = 10, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Recommendation).order_by(desc(Recommendation.run_at)).limit(limit)
    )
    recs = result.scalars().all()
    return [
        {
            "id": r.id,
            "run_at": r.run_at.isoformat(),
            "rule_version": r.rule_version,
            "top_themes": r.top_themes,
        }
        for r in recs
    ]


@router.get("/recommendations/{rec_id}")
async def get_recommendation(rec_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RecommendationItem, Stock)
        .join(Stock, RecommendationItem.stock_id == Stock.id)
        .where(RecommendationItem.recommendation_id == rec_id)
        .order_by(RecommendationItem.priority)
    )
    rows = result.all()

    rec_result = await db.execute(
        select(Recommendation).where(Recommendation.id == rec_id)
    )
    rec = rec_result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    items = [
        {
            "id": ri.id,
            "symbol": s.symbol,
            "name": s.name,
            "action": ri.action,
            "theme_score": ri.theme_score,
            "stock_score": ri.stock_score,
            "reason": ri.reason,
            "price_at_recommendation": ri.price_at_recommendation,
            "was_executed": ri.was_executed,
        }
        for ri, s in rows
    ]

    return {
        "id": rec.id,
        "run_at": rec.run_at.isoformat(),
        "rule_version": rec.rule_version,
        "top_themes": rec.top_themes,
        "items": items,
    }


@router.get("/performance")
async def get_performance_stats(db: AsyncSession = Depends(get_db)):
    tracker = StrategyTracker(db)
    return await tracker.get_stats()


@router.get("/performance/records")
async def list_performance_records(
    limit: int = 50,
    closed_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(PerformanceRecord, Stock).join(
        Stock, PerformanceRecord.stock_id == Stock.id
    )
    if closed_only:
        query = query.where(PerformanceRecord.is_closed == True)
    query = query.order_by(desc(PerformanceRecord.created_at)).limit(limit)

    result = await db.execute(query)
    return [
        {
            "id": p.id,
            "symbol": s.symbol,
            "name": s.name,
            "entry_date": p.entry_date.isoformat() if p.entry_date else None,
            "entry_price": p.entry_price,
            "exit_date": p.exit_date.isoformat() if p.exit_date else None,
            "exit_price": p.exit_price,
            "holding_days": p.holding_days,
            "realized_pnl_pct": p.realized_pnl_pct,
            "max_gain_pct": p.max_gain_pct,
            "max_loss_pct": p.max_loss_pct,
            "is_closed": p.is_closed,
            "score_at_recommendation": p.score_at_recommendation,
            "rule_version": p.rule_version,
            "post_review": p.post_review,
        }
        for p, s in result.all()
    ]


@router.patch("/performance/{record_id}/review")
async def update_review(
    record_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PerformanceRecord).where(PerformanceRecord.id == record_id)
    )
    perf = result.scalar_one_or_none()
    if not perf:
        raise HTTPException(status_code=404, detail="Performance record not found")

    if "post_review" in payload:
        perf.post_review = payload["post_review"]
    if "exit_price" in payload:
        perf.exit_price = payload["exit_price"]

    await db.commit()
    return {"id": record_id, "message": "회고 저장 완료"}


@router.get("/rules")
async def list_strategy_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StrategyRule).order_by(desc(StrategyRule.created_at))
    )
    rules = result.scalars().all()
    return [
        {
            "id": r.id,
            "version": r.version,
            "is_active": r.is_active,
            "description": r.description,
            "parameters": r.parameters,
            "activated_at": r.activated_at.isoformat() if r.activated_at else None,
        }
        for r in rules
    ]


@router.post("/rules")
async def create_strategy_rule(payload: dict, db: AsyncSession = Depends(get_db)):
    tracker = StrategyTracker(db)
    rule = await tracker.activate_strategy_rule(
        version=payload["version"],
        parameters=payload["parameters"],
        description=payload.get("description"),
    )
    return {"id": rule.id, "version": rule.version, "is_active": rule.is_active}


# ══════════════════════════════════════════════
# 전략2: 지수 편입 이벤트
# ══════════════════════════════════════════════

@router.get("/inclusion-events")
async def list_inclusion_events(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """편입 이벤트 목록."""
    query = select(IndexInclusionEvent).order_by(
        IndexInclusionEvent.inclusion_date.asc()
    )
    if status:
        query = query.where(IndexInclusionEvent.status == status)

    result = await db.execute(query)
    return [
        {
            "id": e.id,
            "index_name": e.index_name,
            "symbol": e.symbol,
            "stock_name": e.stock_name,
            "market": e.market,
            "announcement_date": str(e.announcement_date),
            "inclusion_date": str(e.inclusion_date),
            "days_remaining": (e.inclusion_date - date.today()).days,
            "status": e.status,
            "signal_generated": e.signal_generated,
            "source_note": e.source_note,
        }
        for e in result.scalars().all()
    ]


@router.post("/inclusion-events")
async def add_inclusion_event(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """
    편입 이벤트 수동 등록.

    payload 예시:
    {
      "index_name": "SP500",
      "symbol": "AAPL",
      "stock_name": "Apple Inc.",
      "market": "US",
      "announcement_date": "2025-01-10",
      "inclusion_date": "2025-01-17",
      "removal_symbol": "XYZ",
      "source_note": "S&P Dow Jones 공식 발표"
    }
    """
    strategy = IndexInclusionStrategy(db, broker)
    event = await strategy.add_event(
        index_name=payload["index_name"],
        symbol=payload["symbol"],
        stock_name=payload["stock_name"],
        market=payload.get("market", "US"),
        announcement_date=date.fromisoformat(payload["announcement_date"]),
        inclusion_date=date.fromisoformat(payload["inclusion_date"]),
        removal_symbol=payload.get("removal_symbol"),
        source_note=payload.get("source_note"),
    )
    return {
        "id": event.id,
        "symbol": event.symbol,
        "inclusion_date": str(event.inclusion_date),
        "message": "편입 이벤트 등록 완료",
    }


@router.post("/inclusion-events/{event_id}/cancel")
async def cancel_inclusion_event(
    event_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """편입 이벤트 취소 (편입 철회/오류 시)."""
    strategy = IndexInclusionStrategy(db, broker)
    await strategy.cancel_event(event_id, reason=payload.get("reason"))
    return {"id": event_id, "message": "이벤트 취소 완료"}


@router.post("/recommend/run-inclusion")
async def run_inclusion_recommendation(
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """전략2 추천 실행: 활성 편입 이벤트 → 매수 신호 생성."""
    strategy = IndexInclusionStrategy(db, broker)
    rec = await strategy.run()
    return {
        "recommendation_id": rec.id,
        "strategy_type": rec.strategy_type,
        "active_events": rec.top_themes,
        "market_note": rec.market_note,
    }
