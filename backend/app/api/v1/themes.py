from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.api.deps import get_db, get_broker_dep
from app.services.broker.base import BrokerBase
from app.services.recommendation import ThemeScorer, StockScorer
from app.models.theme import Theme, ThemeScore, ThemeStock
from app.models.stock import Stock

router = APIRouter(prefix="/themes", tags=["Themes"])


@router.get("/")
async def list_themes(db: AsyncSession = Depends(get_db)):
    """테마 목록 + 최신 점수."""
    result = await db.execute(
        select(Theme).where(Theme.is_active == True).order_by(Theme.name)
    )
    themes = result.scalars().all()

    out = []
    for t in themes:
        score_result = await db.execute(
            select(ThemeScore)
            .where(ThemeScore.theme_id == t.id)
            .order_by(desc(ThemeScore.scored_at))
            .limit(1)
        )
        score = score_result.scalar_one_or_none()
        out.append({
            "id": t.id,
            "code": t.code,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "latest_score": score.total_score if score else None,
            "rank": score.rank if score else None,
            "scored_at": score.scored_at.isoformat() if score else None,
        })

    out.sort(key=lambda x: x["latest_score"] or 0, reverse=True)
    return out


@router.get("/{theme_code}")
async def get_theme_detail(theme_code: str, db: AsyncSession = Depends(get_db)):
    """테마 상세: 소속 종목 + 점수 이력."""
    result = await db.execute(select(Theme).where(Theme.code == theme_code))
    theme = result.scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    # 소속 종목
    stocks_result = await db.execute(
        select(Stock, ThemeStock)
        .join(ThemeStock, Stock.id == ThemeStock.stock_id)
        .where(ThemeStock.theme_id == theme.id, Stock.is_active == True)
        .order_by(desc(ThemeStock.is_core))
    )
    stocks = [
        {
            "id": s.id,
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market,
            "last_price": s.last_price,
            "is_core": ts.is_core,
            "weight": ts.weight,
        }
        for s, ts in stocks_result.all()
    ]

    # 점수 이력 (최근 30개)
    scores_result = await db.execute(
        select(ThemeScore)
        .where(ThemeScore.theme_id == theme.id)
        .order_by(desc(ThemeScore.scored_at))
        .limit(30)
    )
    scores = [
        {
            "scored_at": sc.scored_at.isoformat(),
            "total_score": sc.total_score,
            "momentum_score": sc.momentum_score,
            "volume_score": sc.volume_score,
            "breadth_score": sc.breadth_score,
            "rank": sc.rank,
        }
        for sc in scores_result.scalars().all()
    ]

    return {
        "id": theme.id,
        "code": theme.code,
        "name": theme.name,
        "description": theme.description,
        "category": theme.category,
        "stocks": stocks,
        "score_history": scores,
    }


@router.post("/score/run")
async def run_theme_scoring(
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """테마 점수 즉시 계산 실행."""
    scorer = ThemeScorer(db, broker)
    scores = await scorer.score_all_themes()
    await scorer.persist_scores(scores)

    return {
        "scored_count": len(scores),
        "top3": [
            {"code": s.theme_code, "name": s.theme_name, "score": s.total_score}
            for s in scores[:3]
        ],
    }


@router.post("/{theme_code}/stocks")
async def add_stock_to_theme(
    theme_code: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """테마에 종목 추가."""
    result = await db.execute(select(Theme).where(Theme.code == theme_code))
    theme = result.scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    symbol = payload.get("symbol", "").upper()
    result = await db.execute(select(Stock).where(Stock.symbol == symbol))
    stock = result.scalar_one_or_none()
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    ts = ThemeStock(
        theme_id=theme.id,
        stock_id=stock.id,
        weight=payload.get("weight", 1.0),
        is_core=payload.get("is_core", False),
    )
    db.add(ts)
    await db.commit()
    return {"message": f"{symbol} added to {theme_code}"}
