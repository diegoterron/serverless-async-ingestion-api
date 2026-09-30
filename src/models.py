from typing import List
from pydantic import BaseModel, Field, field_validator


class OrderItem(BaseModel):
    item_id: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)


class Order(BaseModel):
    order_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    items: List[OrderItem] = Field(..., min_length=1)
    total_amount: float = Field(..., gt=0)
    currency: str = Field(default="EUR", max_length=3)
    created_at: str = Field(...)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.upper()
