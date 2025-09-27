from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from decimal import Decimal

ISO_COUNTRIES = {"ES", "FR", "US", "DE", "IT", "GB", "PT"}

class OrderIn(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    user_id: str = Field(min_length=1, max_length=64)
    amount: float = Field(ge=0)
    country: str = Field(min_length=2, max_length=2)
    created_at: datetime

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        v = v.upper()
        if v not in ISO_COUNTRIES:
            raise ValueError(f"country must be ISO-3166 alpha-2, got {v}")
        return v

class OrderOut(BaseModel):
    order_id: str
    user_id: str
    amount: float
    country: str
    created_at: datetime

    @classmethod
    def from_orm_row(cls, order) -> "OrderOut":
        # amount puede venir como Decimal desde SQLAlchemy/Postgres
        amt = float(order.amount) if isinstance(order.amount, (Decimal,)) else float(order.amount)
        return cls(
            order_id=order.order_id,
            user_id=order.user_id,
            amount=amt,
            country=order.country,
            created_at=order.created_at,
        )
