"""
주문 센터 API.
흐름: 추천 초안 생성 → 1차 확인 → 2차 EXECUTE 승인 → 실주문 전송

kill switch: ORDER_EXECUTION_ENABLED=false (기본)
이중 확인: confirm_execution=True + final_confirm="EXECUTE"
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_broker_dep
from app.services.broker.base import BrokerBase, OrderRequest
from app.models.order import Order, OrderItem
from app.models.stock import Stock
from app.config import get_settings

router = APIRouter(prefix="/orders", tags=["Orders"])
settings = get_settings()


@router.get("/")
async def list_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(20)
    )
    orders = result.scalars().all()
    return [
        {
            "id": o.id,
            "title": o.title,
            "status": o.status,
            "item_count": 0,
            "created_at": o.created_at.isoformat(),
            "executed_at": o.executed_at.isoformat() if o.executed_at else None,
        }
        for o in orders
    ]


@router.post("/")
async def create_order_draft(payload: dict, db: AsyncSession = Depends(get_db)):
    """추천 기반 주문 초안 생성."""
    order = Order(
        title=payload.get("title", f"주문 {datetime.utcnow().strftime('%m/%d %H:%M')}"),
        status="draft",
        note=payload.get("note"),
    )
    db.add(order)
    await db.flush()

    for item_data in payload.get("items", []):
        stock_id = item_data.get("stock_id")
        stock = None

        if stock_id:
            r = await db.execute(select(Stock).where(Stock.id == stock_id))
            stock = r.scalar_one_or_none()
        elif item_data.get("stock_symbol"):
            r = await db.execute(select(Stock).where(Stock.symbol == item_data["stock_symbol"]))
            stock = r.scalar_one_or_none()

        if not stock:
            continue
        stock_id = stock.id

        item = OrderItem(
            order_id=order.id,
            stock_id=stock_id,
            action=item_data["action"],
            order_type=item_data.get("order_type", "limit"),
            quantity=item_data["quantity"],
            price=item_data.get("price"),
            amount=item_data.get("amount"),
            reason=item_data.get("reason"),
            priority=item_data.get("priority", 5),
            recommendation_item_id=item_data.get("recommendation_item_id"),
        )
        db.add(item)

    await db.commit()
    return {"order_id": order.id, "status": "draft", "message": "주문 초안 생성 완료"}


@router.get("/{order_id}")
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order, OrderItem, Stock)
        .join(OrderItem, Order.id == OrderItem.order_id, isouter=True)
        .join(Stock, OrderItem.stock_id == Stock.id, isouter=True)
        .where(Order.id == order_id)
    )
    rows = result.all()
    if not rows:
        raise HTTPException(status_code=404, detail="Order not found")

    order = rows[0][0]
    items = [
        {
            "id": item.id,
            "symbol": stock.symbol if stock else "",
            "name": stock.name if stock else "",
            "action": item.action,
            "order_type": item.order_type,
            "quantity": item.quantity,
            "price": item.price,
            "amount": item.amount,
            "reason": item.reason,
            "priority": item.priority,
            "status": item.status,
            "broker_order_id": item.broker_order_id,
            "filled_quantity": item.filled_quantity,
            "filled_price": item.filled_price,
        }
        for _, item, stock in rows
        if item is not None
    ]

    return {
        "id": order.id,
        "title": order.title,
        "status": order.status,
        "note": order.note,
        "created_at": order.created_at.isoformat(),
        "approved_at": order.approved_at.isoformat() if order.approved_at else None,
        "executed_at": order.executed_at.isoformat() if order.executed_at else None,
        "items": items,
    }


@router.post("/{order_id}/confirm")
async def confirm_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """1차 확인: draft → confirmed."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "draft":
        raise HTTPException(status_code=400, detail=f"Cannot confirm order in status: {order.status}")

    order.status = "confirmed"
    order.approved_at = datetime.utcnow()
    await db.commit()
    return {"order_id": order_id, "status": "confirmed", "message": "1차 확인 완료. 실행하려면 /execute 호출"}


@router.post("/{order_id}/execute")
async def execute_order(
    order_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """
    2차 승인 + 실주문 전송.

    요청 body:
    {
      "confirm_execution": true,
      "final_confirm": "EXECUTE"
    }

    ⚠ ORDER_EXECUTION_ENABLED=true 일 때만 실제 주문 전송.
    """
    # 이중 확인 검증
    if not payload.get("confirm_execution"):
        raise HTTPException(status_code=400, detail="confirm_execution must be true")
    if payload.get("final_confirm") != "EXECUTE":
        raise HTTPException(status_code=400, detail="final_confirm must be exactly 'EXECUTE'")

    # kill switch 확인
    if not settings.order_execution_enabled:
        raise HTTPException(
            status_code=403,
            detail=(
                "ORDER_EXECUTION_ENABLED=false. "
                ".env에서 kill switch를 true로 설정 후 재시작하세요. "
                "⚠ 실전 계좌에 실제 주문이 전송됩니다."
            ),
        )

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != "confirmed":
        raise HTTPException(status_code=400, detail=f"Order must be confirmed first. Current: {order.status}")

    order.status = "executing"
    await db.commit()

    # 항목별 주문 전송
    items_result = await db.execute(
        select(OrderItem, Stock)
        .join(Stock, OrderItem.stock_id == Stock.id)
        .where(OrderItem.order_id == order_id, OrderItem.status == "pending")
        .order_by(OrderItem.priority)
    )
    rows = items_result.all()

    success_count = 0
    fail_count = 0

    for item, stock in rows:
        try:
            order_req = OrderRequest(
                symbol=stock.symbol,
                action=item.action,
                quantity=item.quantity,
                order_type=item.order_type,
                price=int(item.price) if item.price else None,
                account_number=settings.kiwoom_account_number,
            )

            # 단일 주문 금액 한도 검사
            estimated = (item.price or 0) * item.quantity
            if estimated > settings.order_max_amount_krw:
                item.status = "failed"
                item.error_message = f"한도 초과: {estimated:,.0f}원 > {settings.order_max_amount_krw:,.0f}원"
                fail_count += 1
                continue

            result = await broker.place_order(order_req)

            if result.success:
                item.status = "submitted"
                item.broker_order_id = result.broker_order_id
                item.broker_response = result.raw_response
                success_count += 1
            else:
                item.status = "failed"
                item.error_message = result.message
                fail_count += 1

        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)
            fail_count += 1

    order.status = "completed" if fail_count == 0 else "executing"
    order.executed_at = datetime.utcnow()
    await db.commit()

    return {
        "order_id": order_id,
        "success_count": success_count,
        "fail_count": fail_count,
        "status": order.status,
    }


@router.post("/{order_id}/preview")
async def preview_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    broker: BrokerBase = Depends(get_broker_dep),
):
    """주문 실행 전 사전 검증 (실제 전송 없음)."""
    items_result = await db.execute(
        select(OrderItem, Stock)
        .join(Stock, OrderItem.stock_id == Stock.id)
        .where(OrderItem.order_id == order_id)
    )
    rows = items_result.all()

    previews = []
    for item, stock in rows:
        from app.services.broker.base import OrderRequest
        req = OrderRequest(
            symbol=stock.symbol,
            action=item.action,
            quantity=item.quantity,
            order_type=item.order_type,
            price=int(item.price) if item.price else None,
            account_number=settings.kiwoom_account_number,
        )
        preview = await broker.preview_order(req)
        previews.append(preview)

    return {"order_id": order_id, "previews": previews}
