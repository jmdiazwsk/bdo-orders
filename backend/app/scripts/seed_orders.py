#C:\bdo-orders-platform\backend\app\scripts\seed_orders.py
import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_async_session_maker  # ver nota abajo
from app.models.order import Order

# --- NOTA ---
# Si NO tienes un factory del SessionMaker, añade esta función en tu módulo db.session:
#   from sqlalchemy.ext.asyncio import async_sessionmaker
#   AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
#   def get_async_session_maker(): return AsyncSessionLocal
# O si prefieres, importa directamente AsyncSessionLocal aquí.

COUNTRIES = ["ES", "FR", "DE", "IT", "PT", "NL", "SE", "PL", "UK", "US"]

async def ensure_min_orders(session: AsyncSession, n: int = 200) -> None:
    existing = (await session.execute(select(Order))).scalars().first()
    if existing:
        return  # ya hay datos, no sembramos
    now = datetime.now(tz=timezone.utc)
    rows = []
    for i in range(n):
        created_at = now - timedelta(days=random.randint(0, 9), hours=random.randint(0, 23))
        rows.append(Order(
            order_id=f"O-{i+1:06d}",
            user_id=f"U-{random.randint(1, 50):04d}",
            amount=Decimal(str(round(random.uniform(5, 500), 2))),
            country=random.choice(COUNTRIES),
            created_at=created_at,
        ))
    session.add_all(rows)
    await session.commit()

async def main(n: int = 200) -> None:
    SessionLocal = get_async_session_maker()
    async with SessionLocal() as session:
        await ensure_min_orders(session, n=n)

if __name__ == "__main__":
    asyncio.run(main())
