# C:\bdo-orders-platform\backend\app\api\routes\metrics.py
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.order import Order

router = APIRouter(prefix="/metrics", tags=["metrics"])

def _parse_window(window: str) -> timedelta:
    """Parse short window strings like '5m', '1h', '2d' into timedelta; defaults to 5m on errors."""
    if not window:
        return timedelta(minutes=5)
    unit = window[-1].lower()
    try:
        value = int(window[:-1])
    except ValueError:
        return timedelta(minutes=5)

    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    else:
        return timedelta(minutes=5)

@router.get("")
async def get_metrics(
    window: str = Query(default="1h", description="Time window (e.g., '5m', '1h', '2d')"),
    session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Return basic KPIs over a rolling time window."""
    now = datetime.now(tz=timezone.utc)
    window_delta = _parse_window(window)
    window_start = now - window_delta

    # Count of orders within window
    total_orders = (await session.execute(
        select(func.count())
        .select_from(Order)
        .where(Order.created_at >= window_start)
    )).scalar_one()

    # Sum of amounts within window (COALESCE to 0)
    total_amount = (await session.execute(
        select(func.coalesce(func.sum(Order.amount), 0))
        .where(Order.created_at >= window_start)
    )).scalar_one()

    # Top 3 countries by order count within window
    top_countries_rows = (await session.execute(
        select(Order.country, func.count().label("cnt"))
        .where(Order.created_at >= window_start)
        .group_by(Order.country)
        .order_by(func.count().desc())
        .limit(3)
    )).all()
    top_countries = [country for country, _ in top_countries_rows]

    return {
        "count_orders": int(total_orders),
        "sum_amount": float(total_amount),
        "top_countries": top_countries
    }
