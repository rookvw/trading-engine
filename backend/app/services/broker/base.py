"""
브로커 추상 인터페이스.
KiwoomBrokerAdapter가 이를 구현한다.
새 증권사 추가 시 이 인터페이스만 맞추면 된다.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AccountInfo:
    account_number: str
    account_name: str
    account_type: str


@dataclass
class Balance:
    account_number: str
    total_assets: float          # 총자산
    cash_balance: float          # 예수금
    stock_value: float           # 주식 평가금액
    total_pnl: float             # 총 평가손익
    total_pnl_pct: float
    currency: str = "KRW"


@dataclass
class Position:
    symbol: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class Quote:
    symbol: str
    name: str
    current_price: int
    prev_close: int
    change: int
    change_pct: float
    volume: int
    bid: int
    ask: int
    high: int
    low: int
    open: int
    fetched_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class OrderRequest:
    symbol: str
    action: str          # buy | sell
    quantity: int
    order_type: str      # limit | market
    price: int | None    # 지정가 (시장가 시 None)
    account_number: str


@dataclass
class OrderResult:
    success: bool
    broker_order_id: str | None
    message: str
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderStatus:
    broker_order_id: str
    symbol: str
    action: str
    ordered_quantity: int
    filled_quantity: int
    remaining_quantity: int
    avg_filled_price: float | None
    status: str              # submitted | partial | filled | cancelled | rejected
    created_at: datetime | None


class BrokerBase(ABC):
    """모든 브로커 어댑터가 구현해야 하는 인터페이스."""

    @abstractmethod
    async def get_accounts(self) -> list[AccountInfo]:
        ...

    @abstractmethod
    async def get_balance(self, account_number: str) -> Balance:
        ...

    @abstractmethod
    async def get_positions(self, account_number: str) -> list[Position]:
        ...

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        ...

    @abstractmethod
    async def preview_order(self, request: OrderRequest) -> dict[str, Any]:
        """주문 사전 검증 (실제 전송 없음)."""
        ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResult:
        """실주문 전송. kill switch 통과 후에만 호출."""
        ...

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderStatus:
        ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str, account_number: str) -> bool:
        ...
