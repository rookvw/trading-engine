from fastapi import APIRouter
from app.api.v1 import dashboard, themes, portfolio, orders, strategy

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(dashboard.router)
api_router.include_router(themes.router)
api_router.include_router(portfolio.router)
api_router.include_router(orders.router)
api_router.include_router(strategy.router)
