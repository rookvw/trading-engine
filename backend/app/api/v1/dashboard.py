"""
대시보드 API.

반환 구조:
  - market_indicators: VIX, KOSPI, SP500 등 최신값
  - strategies: [S1, S2, S3] 각 전략의 수익률 + 상태 + 최신 신호
  - news_feed: 최신 뉴스 (전략 태그 포함)
  - portfolio_summary: 전략별 자산 요약
"""
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_

from app.api.deps import get_db, get_broker_dep
from app.services.broker.base import BrokerBase
from app.services.news.crawler import MarketIndicatorService
from app.services.portfolio.manager import PortfolioManager
from app.models.strategy import (
    PerformanceRecord, Recommendation, RecommendationItem, IndexInclusionEvent
)
from app.models.news import NewsItem
from app.models.portfolio import PortfolioHolding
from app.models.stock import Stock
from app.config import get_settings

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
settings = get_settings()


@router.get("/")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    today = date.today()
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # ── 시장 지표 ──────────────────────────────────────────
    indicator_svc = MarketIndicatorService(db)
    market_indicators = await indicator_svc.get_latest()

    # ── 전략별 수익률 계산 ─────────────────────────────────
    strategies = []
    for sn in [1, 2]:
        perf = await _calc_strategy_returns(db, sn, today, month_start, year_start)
        strategies.append(perf)

    # S3 placeholder
    strategies.append({
        "number": 3,
        "name": "전략3",
        "description": "준비중",
        "status": "pending",
        "daily_pct": None,
        "monthly_pct": None,
        "yearly_pct": None,
        "open_positions": 0,
        "latest_signal": None,
        "news_count": 0,
    })

    # ── 최신 뉴스 피드 ────────────────────────────────────
    news_result = await db.execute(
        select(NewsItem)
        .order_by(desc(NewsItem.published_at))
        .limit(15)
    )
    news_items = [
        {
            "id": n.id,
            "title": n.title,
            "source": n.source,
            "published_at": n.published_at.isoformat(),
            "strategy_tags": n.strategy_tags,
            "category": n.category,
            "importance": n.importance,
            "sentiment_label": n.sentiment_label,
            "is_actionable": n.is_actionable,
            "url": n.url,
        }
        for n in news_result.scalars().all()
    ]

    # ── 포트폴리오 요약 (전략별) ────────────────────────────
    pm = PortfolioManager(db, broker)
    allocation = await pm.get_allocation_summary()

    holdings_result = await db.execute(
        select(PortfolioHolding, Stock)
        .join(Stock, PortfolioHolding.stock_id == Stock.id)
    )
    by_strategy: dict[int, dict] = {1: {"value": 0, "count": 0}, 2: {"value": 0, "count": 0}, 3: {"value": 0, "count": 0}}
    for h, s in holdings_result.all():
        sn = h.strategy_number or 1
        if sn in by_strategy:
            val = h.current_value or (h.quantity * h.avg_price)
            by_strategy[sn]["value"] += val
            by_strategy[sn]["count"] += 1

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "order_execution_enabled": settings.order_execution_enabled,
        "market_indicators": market_indicators,
        "strategies": strategies,
        "news_feed": news_items,
        "portfolio": {
            "total_value": allocation["total_value"],
            "total_pnl_pct": allocation["total_pnl_pct"],
            "allocations": allocation["allocations"],
            "by_strategy": by_strategy,
        },
    }


@router.get("/news")
async def get_news(
    strategy: int | None = None,
    category: str | None = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """뉴스 피드 — 전략/카테고리 필터."""
    query = select(NewsItem).order_by(desc(NewsItem.published_at)).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()

    filtered = items
    if strategy:
        tag = f"s{strategy}"
        filtered = [n for n in items if tag in (n.strategy_tags or [])]
    if category:
        filtered = [n for n in filtered if n.category == category]

    return [
        {
            "id": n.id,
            "title": n.title,
            "summary": n.summary,
            "source": n.source,
            "url": n.url,
            "published_at": n.published_at.isoformat(),
            "strategy_tags": n.strategy_tags,
            "category": n.category,
            "importance": n.importance,
            "sentiment_label": n.sentiment_label,
            "is_actionable": n.is_actionable,
        }
        for n in filtered
    ]


@router.post("/news")
async def add_news_manual(payload: dict, db: AsyncSession = Depends(get_db)):
    """뉴스 수동 입력 (investing.com 등 직접 입력)."""
    news = NewsItem(
        title=payload["title"],
        summary=payload.get("summary"),
        url=payload.get("url"),
        source=payload.get("source", "manual"),
        published_at=datetime.fromisoformat(payload.get("published_at", datetime.utcnow().isoformat())),
        strategy_tags=payload.get("strategy_tags", []),
        symbols=payload.get("symbols", []),
        category=payload.get("category", "general"),
        importance=payload.get("importance", 2),
        is_actionable=payload.get("is_actionable", False),
        sentiment_label=payload.get("sentiment_label"),
    )
    db.add(news)
    await db.commit()
    return {"id": news.id, "message": "뉴스 등록 완료"}


@router.post("/news/crawl")
async def trigger_crawl(db: AsyncSession = Depends(get_db)):
    """뉴스 크롤링 즉시 실행."""
    from app.services.news.crawler import NewsCrawler
    crawler = NewsCrawler(db)
    count = await crawler.crawl_all()
    return {"new_items": count}


@router.post("/indicators/refresh")
async def refresh_indicators(db: AsyncSession = Depends(get_db)):
    """시장 지표 즉시 갱신 (VIX, KOSPI 등)."""
    svc = MarketIndicatorService(db)
    results = await svc.fetch_all()
    return {"updated": results}


# ── 내부 헬퍼 ──────────────────────────────────────────────

async def _calc_strategy_returns(
    db: AsyncSession,
    strategy_number: int,
    today: date,
    month_start: date,
    year_start: date,
) -> dict:
    """전략별 수익률 집계."""

    STRATEGY_META = {
        1: {
            "name": "전략1 — 테마 모멘텀",
            "description": "공격적 테마 모멘텀 + VIX/뉴스 감성 기반",
        },
        2: {
            "name": "전략2 — 지수 편입",
            "description": "S&P500/KOSPI200 편입 발표 → 패시브 매수 수급 선점",
        },
    }

    meta = STRATEGY_META.get(strategy_number, {"name": f"전략{strategy_number}", "description": ""})

    # 종료된 포지션 수익률 집계
    base_q = select(PerformanceRecord).where(
        and_(
            PerformanceRecord.strategy_number == strategy_number,
            PerformanceRecord.is_closed == True,
            PerformanceRecord.realized_pnl_pct.is_not(None),
        )
    )

    def avg_pnl(records):
        vals = [r.realized_pnl_pct for r in records if r.realized_pnl_pct is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    daily_r = await db.execute(base_q.where(PerformanceRecord.exit_date == today))
    monthly_r = await db.execute(base_q.where(PerformanceRecord.exit_date >= month_start))
    yearly_r = await db.execute(base_q.where(PerformanceRecord.exit_date >= year_start))

    daily_recs = daily_r.scalars().all()
    monthly_recs = monthly_r.scalars().all()
    yearly_recs = yearly_r.scalars().all()

    # 오픈 포지션 수
    open_q = await db.execute(
        select(func.count(PortfolioHolding.id)).where(
            PortfolioHolding.strategy_number == strategy_number
        )
    )
    open_count = open_q.scalar() or 0

    # 최신 추천 신호
    latest_rec_r = await db.execute(
        select(Recommendation)
        .where(Recommendation.strategy_number == strategy_number)
        .order_by(desc(Recommendation.run_at))
        .limit(1)
    )
    latest_rec = latest_rec_r.scalar_one_or_none()

    latest_signal = None
    if latest_rec:
        items_r = await db.execute(
            select(RecommendationItem, Stock)
            .join(Stock, RecommendationItem.stock_id == Stock.id)
            .where(
                and_(
                    RecommendationItem.recommendation_id == latest_rec.id,
                    RecommendationItem.action.in_(["new_entry", "add"]),
                )
            )
            .order_by(RecommendationItem.priority)
            .limit(3)
        )
        latest_signal = [
            {
                "symbol": s.symbol,
                "name": s.name,
                "action": ri.action,
                "sub_strategy": ri.sub_strategy,
                "reason": (ri.reason or "")[:200],
                "current_price": ri.price_at_recommendation,
                "bucket": (ri.score_detail or {}).get("bucket", "theme"),
                "cited_news": (ri.score_detail or {}).get("cited_news", []),
            }
            for ri, s in items_r.all()
        ]

    # 전략2: 활성 편입 이벤트 수
    active_events = 0
    if strategy_number == 2:
        ev_r = await db.execute(
            select(func.count(IndexInclusionEvent.id)).where(
                IndexInclusionEvent.status == "announced"
            )
        )
        active_events = ev_r.scalar() or 0

    # 뉴스 수 (최근 24시간)
    since = datetime.utcnow() - timedelta(hours=24)
    tag = f"s{strategy_number}"
    news_r = await db.execute(
        select(func.count(NewsItem.id)).where(
            NewsItem.published_at >= since
        )
    )
    # 필터는 JSON 필드라 Python에서 처리
    all_recent_news = await db.execute(
        select(NewsItem).where(NewsItem.published_at >= since)
    )
    news_count = sum(1 for n in all_recent_news.scalars().all() if tag in (n.strategy_tags or []))

    return {
        "number": strategy_number,
        "name": meta["name"],
        "description": meta["description"],
        "status": "active",
        "daily_pct": avg_pnl(daily_recs),
        "monthly_pct": avg_pnl(monthly_recs),
        "yearly_pct": avg_pnl(yearly_recs),
        "open_positions": open_count,
        "active_events": active_events if strategy_number == 2 else None,
        "latest_signal": latest_signal,
        "news_count": news_count,
        "last_run": latest_rec.run_at.isoformat() if latest_rec else None,
    }
