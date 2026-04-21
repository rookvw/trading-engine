"""
APScheduler 기반 백그라운드 작업.
macOS/Linux에서 cron 없이 FastAPI 프로세스 내 실행.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import structlog

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.services.broker import get_broker
from app.services.recommendation import ThemeScorer
from app.services.portfolio.manager import PortfolioManager
from app.services.news.crawler import NewsCrawler, MarketIndicatorService

logger = structlog.get_logger()
settings = get_settings()
scheduler = AsyncIOScheduler()


async def _run_theme_scoring() -> None:
    async with AsyncSessionLocal() as db:
        try:
            broker = get_broker()
            scorer = ThemeScorer(db, broker)
            scores = await scorer.score_all_themes()
            await scorer.persist_scores(scores)
            logger.info("scheduled_theme_scoring_done", count=len(scores))
        except Exception as e:
            logger.error("scheduled_theme_scoring_error", error=str(e))


async def _run_portfolio_sync() -> None:
    if not settings.kiwoom_configured:
        return
    async with AsyncSessionLocal() as db:
        try:
            broker = get_broker()
            pm = PortfolioManager(db, broker)
            holdings = await pm.sync_from_broker(settings.kiwoom_account_number)
            logger.info("scheduled_portfolio_sync_done", count=len(holdings))
        except Exception as e:
            logger.error("scheduled_portfolio_sync_error", error=str(e))


async def _run_news_crawl() -> None:
    async with AsyncSessionLocal() as db:
        try:
            crawler = NewsCrawler(db)
            count = await crawler.crawl_all()
            logger.info("scheduled_news_crawl_done", new_items=count)
        except Exception as e:
            logger.error("scheduled_news_crawl_error", error=str(e))


async def _run_market_indicators() -> None:
    async with AsyncSessionLocal() as db:
        try:
            svc = MarketIndicatorService(db)
            results = await svc.fetch_all()
            logger.info("scheduled_indicators_done", indicators=list(results.keys()))
        except Exception as e:
            logger.error("scheduled_indicators_error", error=str(e))


def setup_scheduler() -> None:
    scheduler.add_job(
        _run_theme_scoring,
        trigger=IntervalTrigger(minutes=settings.theme_score_interval_minutes),
        id="theme_scoring",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_portfolio_sync,
        trigger=IntervalTrigger(minutes=settings.portfolio_sync_interval_minutes),
        id="portfolio_sync",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_news_crawl,
        trigger=IntervalTrigger(minutes=15),
        id="news_crawl",
        replace_existing=True,
    )
    scheduler.add_job(
        _run_market_indicators,
        trigger=IntervalTrigger(minutes=5),
        id="market_indicators",
        replace_existing=True,
    )
    logger.info(
        "scheduler_configured",
        theme_interval=settings.theme_score_interval_minutes,
        portfolio_interval=settings.portfolio_sync_interval_minutes,
    )
