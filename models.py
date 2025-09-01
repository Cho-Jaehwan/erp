from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 관계
    product = relationship("Product", back_populates="stock_transactions")
    user = relationship("User", back_populates="stock_transactions")
    supplier = relationship("Supplier", back_populates="stock_transactions")
