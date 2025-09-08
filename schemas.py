from pydantic import BaseModel, EmailStr
from typing import Optional, Union
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
    sort_order: int = 0
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SupplierSortOrderUpdate(BaseModel):
    sort_orders: dict  # {"supplier_id": sort_order}

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

# 다중 제품 입고/출고 처리를 위한 스키마
class BulkStockItem(BaseModel):
    product_id: int
    quantity: int
    lot_number: Optional[str] = None

class BulkStockInCreate(BaseModel):
    items: list[BulkStockItem]
    supplier_id: Optional[int] = None
    notes: Optional[str] = None

class BulkStockOutCreate(BaseModel):
    items: list[BulkStockItem]
    supplier_id: Optional[int] = None
    notes: Optional[str] = None

# 결제 관련 스키마
class PaymentTransactionBase(BaseModel):
    supplier_id: int
    stock_transaction_id: Optional[int] = None
    payment_type: str  # "prepayment", "payment", "settlement"
    amount: float
    currency: str = "KRW"
    payment_method: Optional[str] = None
    payment_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class PaymentTransactionCreate(PaymentTransactionBase):
    pass

class PaymentTransaction(PaymentTransactionBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PaymentScheduleBase(BaseModel):
    supplier_id: int
    stock_transaction_id: Optional[int] = None
    total_amount: float
    due_date: datetime
    payment_terms: Optional[str] = None
    notes: Optional[str] = None

class PaymentScheduleCreate(PaymentScheduleBase):
    pass

class PaymentSchedule(PaymentScheduleBase):
    id: int
    user_id: int
    paid_amount: float
    remaining_amount: float
    status: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PrepaymentBalanceBase(BaseModel):
    supplier_id: int
    balance: float = 0
    currency: str = "KRW"

class PrepaymentBalanceCreate(PrepaymentBalanceBase):
    pass

class PrepaymentBalance(PrepaymentBalanceBase):
    id: int
    total_prepaid: float
    total_used: float
    is_active: bool
    last_updated: datetime
    created_at: datetime
    
    class Config:
        from_attributes = True

# 새로운 주문 관리 시스템 스키마
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int
    unit_price: float
    notes: Optional[str] = None

class OrderItemCreate(OrderItemBase):
    pass

class OrderItem(OrderItemBase):
    id: int
    order_id: int
    total_price: float
    supplied_quantity: int
    remaining_quantity: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class OrderBase(BaseModel):
    supplier_id: int
    delivery_date: Optional[Union[datetime, str]] = None
    total_amount: float
    currency: str = "KRW"
    priority: str = "normal"
    payment_type: str = "post"
    notes: Optional[str] = None

class OrderCreate(OrderBase):
    items: list[OrderItemCreate]

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    delivery_date: Optional[datetime] = None
    priority: Optional[str] = None
    notes: Optional[str] = None

class Order(OrderBase):
    id: int
    order_number: str
    user_id: int
    order_date: datetime
    status: str
    payment_type: str
    created_at: datetime
    updated_at: datetime
    order_items: list[OrderItem] = []
    
    class Config:
        from_attributes = True

class AdvancePaymentBase(BaseModel):
    order_id: int
    amount: float
    currency: str = "KRW"
    payment_method: Optional[str] = None
    payment_date: Optional[datetime] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class AdvancePaymentCreate(AdvancePaymentBase):
    pass

class AdvancePaymentUpdate(BaseModel):
    status: Optional[str] = None
    payment_date: Optional[datetime] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None

class AdvancePayment(AdvancePaymentBase):
    id: int
    user_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class SupplyScheduleBase(BaseModel):
    order_id: int
    schedule_date: datetime
    planned_quantity: int
    notes: Optional[str] = None

class SupplyScheduleCreate(SupplyScheduleBase):
    pass

class SupplyScheduleUpdate(BaseModel):
    actual_quantity: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class SupplySchedule(SupplyScheduleBase):
    id: int
    user_id: int
    actual_quantity: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class DocumentWorkBase(BaseModel):
    order_id: int
    document_type: str
    due_date: Optional[datetime] = None
    notes: Optional[str] = None

class DocumentWorkCreate(DocumentWorkBase):
    pass

class DocumentWorkUpdate(BaseModel):
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    notes: Optional[str] = None
    file_path: Optional[str] = None

class DocumentWork(DocumentWorkBase):
    id: int
    user_id: int
    status: str
    start_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True