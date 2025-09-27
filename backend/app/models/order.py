from sqlalchemy import String, Numeric, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from backend.app.db.session import Base
from sqlalchemy import DateTime
from datetime import datetime
from sqlalchemy import CheckConstraint

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    country: Mapped[str] = mapped_column(String(2), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_orders_country_created_at", "country", "created_at"),
        CheckConstraint("char_length(country) = 2", name="ck_country_len_2"),
    )