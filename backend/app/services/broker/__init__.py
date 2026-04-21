from app.services.broker.base import (
    BrokerBase, AccountInfo, Balance, Position, Quote,
    OrderRequest, OrderResult, OrderStatus,
)
from app.services.broker.kiwoom import KiwoomBrokerAdapter
from app.services.broker.demo import DemoBroker
from app.config import get_settings
from functools import lru_cache


@lru_cache
def get_broker() -> BrokerBase:
    s = get_settings()
    if s.kiwoom_app_key and s.kiwoom_app_secret and s.kiwoom_app_key != "your_app_key_here":
        return KiwoomBrokerAdapter()
    return DemoBroker()


__all__ = [
    "BrokerBase", "AccountInfo", "Balance", "Position", "Quote",
    "OrderRequest", "OrderResult", "OrderStatus",
    "KiwoomBrokerAdapter", "DemoBroker", "get_broker",
]
