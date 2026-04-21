from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, Integer, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Order(Base):
    """주문 세션. 하나의 리밸런싱 라운드 단위."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft"
        # draft | confirmed | executing | completed | cancelled
    )
    approved_by: Mapped[str | None] = mapped_column(String(100))   # 1차 확인
    executed_by: Mapped[str | None] = mapped_column(String(100))   # 2차 실행 승인
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list[OrderItem]] = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    """개별 주문 항목. 1 Order : N OrderItem."""

    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"), nullable=False)

    # 주문 내용
    action: Mapped[str] = mapped_column(
        String(10), nullable=False
        # buy | sell
    )
    order_type: Mapped[str] = mapped_column(
        String(20), default="limit"
        # limit | market
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float | None] = mapped_column(Float)                 # 지정가 (시장가시 null)
    amount: Mapped[float | None] = mapped_column(Float)               # 예상 금액

    # 추천 근거
    reason: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=5)         # 1(필수) ~ 10(선택)
    recommendation_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("recommendation_items.id")
    )

    # 실행 결과
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
        # pending | submitted | filled | partial | failed | cancelled
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(50))   # 키움 주문번호
    filled_quantity: Mapped[int | None] = mapped_column(Integer)
    filled_price: Mapped[float | None] = mapped_column(Float)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    broker_response: Mapped[dict | None] = mapped_column(JSON)         # 키움 응답 원문

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    order: Mapped[Order] = relationship("Order", back_populates="items")
    stock: Mapped["Stock"] = relationship("Stock")
    recommendation_item: Mapped["RecommendationItem | None"] = relationship(
        "RecommendationItem"
    )
