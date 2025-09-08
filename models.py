from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_approved = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    stock_transactions = relationship("StockTransaction", back_populates="user")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    price = Column(Float, nullable=False)
    stock_quantity = Column(Integer, default=0)
    safety_stock = Column(Integer, default=0)  # 안전 재고 수준
    safety_stock_level = Column(String(20), default="good")  # 안전 재고 단계: good, warning, critical
    category = Column(String(50), index=True)
    sort_order = Column(Integer, default=0)  # 카테고리 내 정렬 순서
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    stock_transactions = relationship("StockTransaction", back_populates="product")

class Supplier(Base):
    __tablename__ = "suppliers"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    contact_person = Column(String(100))
    phone = Column(String(20))
    email = Column(String(100))
    address = Column(Text)
    supplier_type = Column(String(20), nullable=False)  # "in" (입고처) 또는 "out" (출고처)
    sort_order = Column(Integer, default=0)  # 거래처 정렬 순서
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    stock_transactions = relationship("StockTransaction", back_populates="supplier")

class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    transaction_type = Column(String(10), nullable=False)  # "in" 또는 "out"
    quantity = Column(Integer, nullable=False)
    lot_number = Column(String(50), nullable=True)  # LOT 번호
    location = Column(String(100), nullable=True)  # 입고처/출고처 (레거시 필드)
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    product = relationship("Product", back_populates="stock_transactions")
    user = relationship("User", back_populates="stock_transactions")
    supplier = relationship("Supplier", back_populates="stock_transactions")

class CategoryOrder(Base):
    __tablename__ = "category_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    category_name = Column(String(50), unique=True, nullable=False, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # "DELETE_TRANSACTION", "CREATE_TRANSACTION" 등
    target_type = Column(String(50), nullable=False)  # "StockTransaction", "Product" 등
    target_id = Column(Integer, nullable=True)  # 대상 객체의 ID
    details = Column(Text)  # 상세 정보 (JSON 형태)
    ip_address = Column(String(45))  # IPv4 또는 IPv6
    user_agent = Column(Text)  # 브라우저 정보
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    user = relationship("User")

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_transaction_id = Column(Integer, ForeignKey("stock_transactions.id"), nullable=True)
    
    # 결제 정보
    payment_type = Column(String(20), nullable=False)  # "prepayment", "payment", "settlement"
    amount = Column(Float, nullable=False)  # 결제 금액
    currency = Column(String(3), default="KRW")  # 통화 (기본: 원화)
    
    # 결제 상태
    status = Column(String(20), default="pending")  # "pending", "completed", "cancelled"
    payment_method = Column(String(50))  # "cash", "transfer", "card", "check"
    
    # 날짜 정보
    payment_date = Column(DateTime)  # 실제 결제일
    due_date = Column(DateTime)  # 결제 예정일 (후납의 경우)
    
    # 추가 정보
    reference_number = Column(String(100))  # 거래 참조번호
    notes = Column(Text)  # 비고
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    supplier = relationship("Supplier")
    user = relationship("User")
    stock_transaction = relationship("StockTransaction")

class PaymentSchedule(Base):
    __tablename__ = "payment_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stock_transaction_id = Column(Integer, ForeignKey("stock_transactions.id"), nullable=True)
    
    # 스케줄 정보
    total_amount = Column(Float, nullable=False)  # 총 결제 예정 금액
    paid_amount = Column(Float, default=0)  # 이미 지급된 금액
    remaining_amount = Column(Float, nullable=False)  # 남은 금액
    
    # 일정 정보
    due_date = Column(DateTime, nullable=False)  # 결제 예정일
    payment_terms = Column(String(50))  # "30일", "60일", "현금" 등
    
    # 상태
    status = Column(String(20), default="pending")  # "pending", "partial", "completed", "overdue"
    is_active = Column(Boolean, default=True)
    
    # 추가 정보
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    supplier = relationship("Supplier")
    user = relationship("User")
    stock_transaction = relationship("StockTransaction")

class PrepaymentBalance(Base):
    __tablename__ = "prepayment_balances"
    
    id = Column(Integer, primary_key=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False, unique=True)
    
    # 잔액 정보
    balance = Column(Float, default=0)  # 현재 선납금 잔액
    total_prepaid = Column(Float, default=0)  # 총 선납금
    total_used = Column(Float, default=0)  # 총 사용된 선납금
    
    # 통화
    currency = Column(String(3), default="KRW")
    
    # 상태
    is_active = Column(Boolean, default=True)
    
    # 날짜
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    supplier = relationship("Supplier")

# 새로운 주문 관리 시스템
class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)  # 주문번호
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 주문 정보
    order_date = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    delivery_date = Column(DateTime)  # 납기일
    total_amount = Column(Float, nullable=False)  # 총 주문 금액
    currency = Column(String(3), default="KRW")
    
    # 주문 상태
    status = Column(String(20), default="pending")  # pending, confirmed, in_progress, completed, cancelled
    priority = Column(String(10), default="normal")  # low, normal, high, urgent
    payment_type = Column(String(10), default="post")  # advance, post
    
    # 추가 정보
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    supplier = relationship("Supplier")
    user = relationship("User")
    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    advance_payments = relationship("AdvancePayment", back_populates="order", cascade="all, delete-orphan")
    supply_schedules = relationship("SupplySchedule", back_populates="order", cascade="all, delete-orphan")

class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    
    # 주문 상품 정보
    quantity = Column(Integer, nullable=False)  # 주문 수량
    unit_price = Column(Float, nullable=False)  # 단가
    total_price = Column(Float, nullable=False)  # 총 가격 (quantity * unit_price)
    
    # 공급 정보
    supplied_quantity = Column(Integer, default=0)  # 이미 공급된 수량
    remaining_quantity = Column(Integer, nullable=False)  # 남은 공급 수량
    
    # 추가 정보
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    order = relationship("Order", back_populates="order_items")
    product = relationship("Product")

class AdvancePayment(Base):
    __tablename__ = "advance_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 선납금 정보
    amount = Column(Float, nullable=False)  # 선납금 금액
    currency = Column(String(3), default="KRW")
    payment_method = Column(String(50))  # cash, transfer, card, check
    
    # 결제 상태
    status = Column(String(20), default="pending")  # pending, completed, cancelled, refunded
    payment_date = Column(DateTime)  # 실제 결제일
    
    # 참조 정보
    reference_number = Column(String(100))  # 거래 참조번호
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    order = relationship("Order", back_populates="advance_payments")
    user = relationship("User")

class SupplySchedule(Base):
    __tablename__ = "supply_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 공급 일정 정보
    schedule_date = Column(DateTime, nullable=False)  # 공급 예정일
    planned_quantity = Column(Integer, nullable=False)  # 계획된 공급 수량
    actual_quantity = Column(Integer, default=0)  # 실제 공급 수량
    
    # 공급 상태
    status = Column(String(20), default="scheduled")  # scheduled, in_progress, completed, cancelled, delayed
    
    # 추가 정보
    notes = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    order = relationship("Order", back_populates="supply_schedules")
    user = relationship("User")

class DocumentWork(Base):
    __tablename__ = "document_works"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 문서 작업 정보
    document_type = Column(String(50), nullable=False)  # contract, invoice, delivery_note, etc.
    status = Column(String(20), default="pending")  # pending, in_progress, completed, rejected
    
    # 날짜 정보
    start_date = Column(DateTime)
    completion_date = Column(DateTime)
    due_date = Column(DateTime)  # 완료 예정일
    
    # 추가 정보
    notes = Column(Text)
    file_path = Column(String(500))  # 첨부 파일 경로
    created_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone(timedelta(hours=9))), onupdate=lambda: datetime.now(timezone(timedelta(hours=9))))
    
    # 관계
    order = relationship("Order")
    user = relationship("User")