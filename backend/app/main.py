import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.api.v1.router import api_router
from app.tasks.scheduler import scheduler, setup_scheduler

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_starting", env=settings.app_env)
    await create_tables()
    setup_scheduler()
    scheduler.start()
    logger.info(
        "app_ready",
        order_execution_enabled=settings.order_execution_enabled,
        kiwoom_configured=settings.kiwoom_configured,
    )
    yield
    scheduler.shutdown()
    logger.info("app_shutdown")


app = FastAPI(
    title="실전 투자 운영 앱",
    description="ETF 20 / 배당 30 / 테마 50 포트폴리오 운영",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "env": settings.app_env,
        "order_execution": settings.order_execution_enabled,
        "kiwoom_ready": settings.kiwoom_configured,
    }
