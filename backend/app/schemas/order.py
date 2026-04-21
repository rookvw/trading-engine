from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_id: int
    symbol: str
    name: str
    action: str
    order_type: str
    quantity: int
    price: float | None
    amount: float | None
    reason: str | None
    priority: int
    status: str
    broker_order_id: str | None
    filled_quantity: int | None
    filled_price: float | None
    filled_at: datetime | None
    error_message: str | None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    approved_at: datetime | None
    executed_at: datetime | None
    note: str | None
    created_at: datetime
    items: list[OrderItemOut] = []


class OrderItemCreate(BaseModel):
    stock_id: int
    action: str          # buy | sell
    order_type: str = "limit"
    quantity: int
    price: float | None = None
    reason: str | None = None
    priority: int = 5
    recommendation_item_id: int | None = None


class OrderCreateRequest(BaseModel):
    title: str
    items: list[OrderItemCreate]
    note: str | None = None


class PlaceOrderRequest(BaseModel):
    """실주문 최종 전송 요청. 2단계 확인 필수."""

    order_id: int
    confirm_execution: bool   # 1차: True로 설정해야만 진행
    final_confirm: str        # 2차: "EXECUTE" 문자열 입력 필수

    @field_validator("final_confirm")
    @classmethod
    def validate_final_confirm(cls, v: str) -> str:
        if v != "EXECUTE":
            raise ValueError("final_confirm must be exactly 'EXECUTE'")
        return v
