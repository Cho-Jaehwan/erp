from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# 사용자 관련 스키마
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class User(UserBase):
    id: int
    is_approved: bool
    is_admin: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# 제품 관련 스키마
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock_quantity: int = 0
    safety_stock: int = 0
    category: Optional[str] = None

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    safety_stock: int = 0
    safety_stock_level: str = "good"  # good, warning, critical
    category: Optional[str] = None

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None

class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 거래처 관련 스키마
class SupplierBase(BaseModel):
    name: str
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    supplier_type: str  # "in" 또는 "out"

class SupplierCreate(SupplierBase):
    pass

class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    supplier_type: Optional[str] = None
    is_active: Optional[bool] = None

class Supplier(SupplierBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# 재고 거래 관련 스키마
class StockTransactionBase(BaseModel):
    product_id: int
    quantity: int
    lot_number: Optional[str] = None
    supplier_id: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None

class StockTransactionCreate(StockTransactionBase):
    pass

class StockTransaction(StockTransactionBase):
    id: int
    user_id: int
    transaction_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# 다중 제품 출고 처리를 위한 스키마
class BulkStockOutItem(BaseModel):
    product_id: int
    quantity: int
    lot_number: Optional[str] = None

class BulkStockOutCreate(BaseModel):
    items: list[BulkStockOutItem]
    supplier_id: Optional[int] = None
    notes: Optional[str] = None