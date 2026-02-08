from pydantic import BaseModel
from typing import Optional


class ProjectCreate(BaseModel):
    name: str

class ShelfCreate(BaseModel):
    name: str

class BinCreate(BaseModel):
    bin_code: str
    label: str | None = None
    product_name: str | None = None
    qty: int | None = None
    description: str | None = None

class BinPatch(BaseModel):
    label: Optional[str] = None
    product_name: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[int] = None
    sku: Optional[str] = None
