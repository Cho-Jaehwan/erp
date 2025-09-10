from fastapi import FastAPI, Request, Depends, HTTPException, status, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text
import uvicorn
from datetime import datetime, timedelta
from typing import List, Optional
import os
import io
import csv
import pytz

from database import get_db, engine
from models import User, Product, StockTransaction, Supplier, AuditLog, CategoryOrder, PaymentTransaction, PaymentSchedule, PrepaymentBalance, Order, OrderItem, AdvancePayment, SupplySchedule, DocumentWork, Base
from auth import get_current_user, get_current_admin, create_access_token, create_refresh_token, verify_password, get_password_hash
from schemas import UserCreate, UserLogin, ProductCreate, ProductUpdate, StockTransactionCreate, StockTransactionQuantityUpdate, SupplierCreate, SupplierUpdate, BulkStockInCreate, BulkStockOutCreate, PaymentTransactionCreate, PaymentScheduleCreate, PrepaymentBalanceCreate, OrderCreate, OrderUpdate, AdvancePaymentCreate, AdvancePaymentUpdate, SupplyScheduleCreate, SupplyScheduleUpdate, DocumentWorkCreate, DocumentWorkUpdate
import subprocess
import sys

def check_database_exists():
    """데이터베이스 파일 존재 여부 확인"""
    from database import DB_DIR
    db_path = os.path.join(DB_DIR, "erp_system.db")
    return os.path.exists(db_path)

def ensure_all_tables_exist():
    """모든 필요한 테이블이 존재하는지 확인하고 없으면 생성"""
    try:
        from database import SessionLocal, engine
        db = SessionLocal()
        
        # 모든 테이블 존재 여부 확인
        required_tables = [
            'users', 'products', 'suppliers', 'stock_transactions', 
            'audit_logs', 'orders', 'order_items', 'advance_payments',
            'supply_schedules', 'document_works', 'payment_transactions',
            'payment_schedules', 'prepayment_balances', 'category_orders'
        ]
        
        missing_tables = []
        for table in required_tables:
            try:
                db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
            except Exception:
                missing_tables.append(table)
        
        db.close()
        
        if missing_tables:
            print(f"누락된 테이블들: {missing_tables}")
            print("모든 테이블을 생성합니다...")
            Base.metadata.create_all(bind=engine)
            print("모든 테이블 생성 완료!")
            return True
        else:
            print("모든 테이블이 존재합니다.")
            return True
            
    except Exception as e:
        print(f"테이블 확인 중 오류: {e}")
        # 오류가 발생해도 테이블 생성 시도
        try:
            Base.metadata.create_all(bind=engine)
            print("오류 발생으로 인한 테이블 생성 완료!")
            return True
        except Exception as create_error:
            print(f"테이블 생성 실패: {create_error}")
            return False

def check_audit_logs_table_exists():
    """audit_logs 테이블 존재 여부 확인"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1 FROM audit_logs LIMIT 1"))
        db.close()
        return True
    except Exception:
        return False

def check_sort_order_column_exists():
    """products 테이블에 sort_order 컬럼 존재 여부 확인"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        result = db.execute(text("PRAGMA table_info(products)"))
        columns = result.fetchall()
        db.close()
        
        # 컬럼명 확인
        column_names = [column[1] for column in columns]
        return 'sort_order' in column_names
    except Exception:
        return False

def check_supplier_sort_order_column_exists():
    """suppliers 테이블에 sort_order 컬럼 존재 여부 확인"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        result = db.execute(text("PRAGMA table_info(suppliers)"))
        columns = result.fetchall()
        db.close()
        
        # 컬럼명 확인
        column_names = [column[1] for column in columns]
        return 'sort_order' in column_names
    except Exception:
        return False

def check_category_orders_table_exists():
    """category_orders 테이블 존재 여부 확인"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1 FROM category_orders LIMIT 1"))
        db.close()
        return True
    except Exception:
        return False

def check_payment_tables_exist():
    """결제 관련 테이블들 존재 여부 확인"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        # 각 테이블 존재 여부 확인
        tables = ["payment_transactions", "payment_schedules", "prepayment_balances"]
        for table in tables:
            db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
        
        db.close()
        return True
    except Exception:
        return False

def check_order_tables_exist():
    """주문 관련 테이블들 존재 여부 확인"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        # 각 테이블 존재 여부 확인
        tables = ["orders", "order_items", "advance_payments", "supply_schedules", "document_works"]
        for table in tables:
            db.execute(text(f"SELECT 1 FROM {table} LIMIT 1"))
        
        db.close()
        return True
    except Exception:
        return False

def migrate_add_sort_order():
    """Product 테이블에 sort_order 컬럼을 추가하고 기존 데이터에 순서를 설정합니다."""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        print("sort_order 컬럼을 추가하는 중...")
        db.execute(text("ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0"))
        
        # 기존 제품들에 카테고리별 순서 설정
        print("기존 제품들에 순서를 설정하는 중...")
        
        # 카테고리별로 제품 조회
        result = db.execute(text("""
            SELECT id, category, name 
            FROM products 
            ORDER BY category, name
        """))
        products = result.fetchall()
        
        # 카테고리별 순서 카운터
        category_counters = {}
        
        for product_id, category, name in products:
            category_key = category or '미분류'
            
            if category_key not in category_counters:
                category_counters[category_key] = 0
            
            category_counters[category_key] += 1
            sort_order = category_counters[category_key]
            
            # sort_order 업데이트
            db.execute(text("""
                UPDATE products 
                SET sort_order = :sort_order 
                WHERE id = :product_id
            """), {"sort_order": sort_order, "product_id": product_id})
            
            print(f"제품 '{name}' (카테고리: {category_key}) -> 순서: {sort_order}")
        
        # 변경사항 저장
        db.commit()
        print(f"마이그레이션 완료! 총 {len(products)}개 제품의 순서가 설정되었습니다.")
        
        return True
        
    except Exception as e:
        print(f"마이그레이션 중 오류 발생: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

def migrate_add_supplier_sort_order():
    """Supplier 테이블에 sort_order 컬럼을 추가하고 기존 데이터에 순서를 설정합니다."""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        print("거래처 sort_order 컬럼을 추가하는 중...")
        db.execute(text("ALTER TABLE suppliers ADD COLUMN sort_order INTEGER DEFAULT 0"))
        
        # 기존 거래처들에 타입별 순서 설정
        print("기존 거래처들에 순서를 설정하는 중...")
        
        # 타입별로 거래처 조회
        result = db.execute(text("""
            SELECT id, supplier_type, name 
            FROM suppliers 
            ORDER BY supplier_type, name
        """))
        suppliers = result.fetchall()
        
        # 타입별 순서 카운터
        type_counters = {}
        
        for supplier_id, supplier_type, name in suppliers:
            if supplier_type not in type_counters:
                type_counters[supplier_type] = 0
            
            type_counters[supplier_type] += 1
            sort_order = type_counters[supplier_type]
            
            # sort_order 업데이트
            db.execute(text("""
                UPDATE suppliers 
                SET sort_order = :sort_order 
                WHERE id = :supplier_id
            """), {"sort_order": sort_order, "supplier_id": supplier_id})
            
        
        # 변경사항 저장
        db.commit()
        
        return True
        
    except Exception as e:
        print(f"마이그레이션 중 오류 발생: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def initialize_category_orders():
    """카테고리 순서를 초기화합니다. (기존 데이터가 없을 때만)"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        # category_orders 테이블이 존재하지 않으면 생성
        if not check_category_orders_table_exists():
            print("category_orders 테이블이 없습니다. 생성합니다.")
            Base.metadata.create_all(bind=engine)
        
        # 기존 카테고리 순서 데이터가 있는지 확인
        existing_orders = db.query(CategoryOrder).count()
        if existing_orders > 0:
            return True
        
        # 현재 존재하는 모든 카테고리 조회
        result = db.execute(text("""
            SELECT DISTINCT category 
            FROM products 
            WHERE category IS NOT NULL
            ORDER BY category
        """))
        categories = [row[0] for row in result.fetchall()]
        
        # 미분류 카테고리도 추가
        categories.append('미분류')
        
        # 카테고리 순서 설정
        for index, category in enumerate(categories):
            category_order = CategoryOrder(
                category_name=category,
                sort_order=index + 1
            )
            db.add(category_order)
            print(f"카테고리 '{category}' -> 순서: {index + 1}")
        
        db.commit()
        print(f"카테고리 순서 초기화 완료! 총 {len(categories)}개 카테고리의 순서가 설정되었습니다.")
        
        return True
        
    except Exception as e:
        print(f"카테고리 순서 초기화 중 오류 발생: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()

def migrate_supplier_type():
    """거래처 유형 마이그레이션"""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        # supplier_type 컬럼이 없는 거래처들 확인
        result = db.execute(text("""
            SELECT id, name, supplier_type 
            FROM suppliers 
            WHERE supplier_type IS NULL OR supplier_type = ''
        """))
        suppliers_without_type = result.fetchall()
        
        if suppliers_without_type:
            print(f"supplier_type이 없는 거래처 {len(suppliers_without_type)}개를 발견했습니다.")
            
            for supplier_id, name, current_type in suppliers_without_type:
                # 기본값으로 'out' (입고처) 설정
                db.execute(text("""
                    UPDATE suppliers 
                    SET supplier_type = 'out' 
                    WHERE id = :supplier_id
                """), {"supplier_id": supplier_id})
                print(f"거래처 '{name}' (ID: {supplier_id})의 유형을 '출고처처'로 설정했습니다.")
            
            db.commit()
            print("거래처 유형 마이그레이션이 완료되었습니다.")
            return True
        else:
            print("마이그레이션이 필요한 거래처가 없습니다.")
            return True
            
    except Exception as e:
        print(f"거래처 유형 마이그레이션 중 오류: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def initialize_database():
    """데이터베이스 초기화"""  # 먼저 테이블 생성 (데이터베이스 파일이 없어도 생성됨)  
    
    if not check_database_exists():
        print("데이터베이스가 없습니다. 초기화를 시작합니다...")
        try:
            # init_admin.py 실행
            result = subprocess.run([sys.executable, "init_admin.py"], 
                                  capture_output=True, text=True, check=True)
            print("데이터베이스 초기화 완료:")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"데이터베이스 초기화 실패: {e}")
            print(f"에러 출력: {e.stderr}")
            sys.exit(1)
    else:
        print("기존 데이터베이스를 사용합니다.")
        init_audit_logs_table()
    
    # sort_order 컬럼 마이그레이션 확인 및 실행
    if not check_sort_order_column_exists():
        print("sort_order 컬럼이 없습니다. 마이그레이션을 시작합니다...")
        if migrate_add_sort_order():
            print("sort_order 컬럼 마이그레이션이 완료되었습니다.")
        else:
            print("❌ sort_order 컬럼 마이그레이션에 실패했습니다.")
    else:
        print("sort_order 컬럼이 이미 존재합니다.")
    
    # 거래처 유형 마이그레이션
    print("거래처 유형 마이그레이션을 확인합니다...")
    try:
        if migrate_supplier_type():
            print("거래처 유형 마이그레이션이 완료되었습니다.")
        else:
            print("❌ 거래처 유형 마이그레이션에 실패했습니다.")
    except Exception as e:
        print(f"❌ 거래처 유형 마이그레이션 중 예외 발생: {e}")
    
    # 카테고리 순서 초기화
    print("카테고리 순서를 초기화합니다...")
    try:
        if initialize_category_orders():
            print("카테고리 순서 초기화가 완료되었습니다.")
        else:
            print("❌ 카테고리 순서 초기화에 실패했습니다.")
    except Exception as e:
        print(f"❌ 카테고리 순서 초기화 중 예외 발생: {e}")
        # 카테고리 순서 초기화 실패해도 애플리케이션은 계속 실행

def init_audit_logs_table():
    """감사 로그 테이블 생성"""
    if not check_audit_logs_table_exists():
        print("감사 로그 테이블이 없습니다. 생성합니다.")
        Base.metadata.create_all(bind=engine)
        print("감사 로그 테이블 생성 완료")

# 애플리케이션 시작 전 데이터베이스 초기화
initialize_database()

app = FastAPI(title="웹 기반 재고관리 시스템", description="웹 기반 재고관리 시스템")

# 서울 시간대 설정
SEOUL_TZ = pytz.timezone('Asia/Seoul')

def get_seoul_time():
    """서울 시간을 반환합니다."""
    seoul_time = datetime.now(SEOUL_TZ)

    return seoul_time

def parse_date_with_timezone(date_string: str) -> datetime:
    """날짜 문자열을 서울 시간대로 파싱합니다."""
    try:
        # 날짜만 있는 경우 (YYYY-MM-DD)
        if len(date_string) == 10:
            naive_date = datetime.strptime(date_string, "%Y-%m-%d")
            localized_date = SEOUL_TZ.localize(naive_date)

            return localized_date
        # 날짜와 시간이 있는 경우
        else:
            naive_date = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            localized_date = SEOUL_TZ.localize(naive_date)

            return localized_date
    except ValueError:
        raise ValueError(f"잘못된 날짜 형식입니다: {date_string}")

def format_datetime_for_display(dt: datetime) -> str:
    """datetime 객체를 한국 시간대로 포맷팅하여 반환합니다."""
    if dt.tzinfo is None:
        # naive datetime인 경우 서울 시간대로 변환
        dt = SEOUL_TZ.localize(dt)
    else:
        # 다른 시간대인 경우 서울 시간대로 변환
        dt = dt.astimezone(SEOUL_TZ)
    
    return dt.strftime('%Y-%m-%d %H:%M:%S')

# 정적 파일과 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 쿠키 기반 인증 헬퍼 함수
def get_current_user_from_cookie(access_token: str = Cookie(None), refresh_token: str = Cookie(None)):

    
    if not access_token and not refresh_token:

        return None
    
    from auth import verify_token, verify_refresh_token, is_token_expired, create_access_token
    from database import SessionLocal
    
    # 액세스 토큰이 있고 유효한 경우
    if access_token and not is_token_expired(access_token):
        username = verify_token(access_token)
        if username:
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_approved:

                    return user
            except Exception as e:
                print(f"DEBUG: 데이터베이스 조회 중 오류: {e}")
            finally:
                db.close()
    
    # 액세스 토큰이 만료되었거나 없고, 리프레시 토큰이 있는 경우
    if refresh_token and refresh_token != "None":
        username = verify_refresh_token(refresh_token)
        if username:

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_approved:

                    return user
            except Exception as e:
                print(f"DEBUG: 데이터베이스 조회 중 오류: {e}")
            finally:
                db.close()
    

    return None

# 메인 페이지 - 로그인 페이지로 리다이렉트
@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/login", status_code=302)

# 로그인 페이지
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# 로그인 처리
@app.post("/login")
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_credentials.username).first()
    
    if not user or not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="잘못된 사용자명 또는 비밀번호"
        )
    
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 승인이 필요합니다"
        )
    
    # 액세스 토큰과 리프레시 토큰 생성
    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    response = RedirectResponse(url="/dashboard", status_code=302)
    
    # 액세스 토큰 쿠키 (7일)
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=False,  # JavaScript에서 접근 가능하도록
        max_age=604800,  # 7일 (7 * 24 * 60 * 60)
        secure=False,    # HTTP 환경에서도 작동하도록
        samesite="lax"   # CSRF 보호
    )
    
    # 리프레시 토큰 쿠키 (30일)
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True,   # 보안을 위해 JavaScript에서 접근 불가
        max_age=2592000, # 30일 (30 * 24 * 60 * 60)
        secure=False,    # HTTP 환경에서도 작동하도록
        samesite="lax"   # CSRF 보호
    )
    
    return response

# 회원가입 페이지
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

# 승인 대기 페이지
@app.get("/pending-approval", response_class=HTMLResponse)
async def pending_approval_page(request: Request):
    return templates.TemplateResponse("pending_approval.html", {"request": request})

# 회원가입 처리
@app.post("/register")
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # 사용자명 중복 확인
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 사용자명입니다")
    
    # 이메일 중복 확인
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="이미 등록된 이메일입니다")
    
    # 새 사용자 생성 (승인 대기 상태)
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        is_approved=False,
        is_admin=False
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    response = RedirectResponse(url="/pending-approval", status_code=302)
    return response

# 로그아웃
@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="access_token")
    response.delete_cookie(key="refresh_token")
    return response

# 대시보드
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    db = next(get_db())
    
    # 기본 통계 데이터
    total_products = db.query(Product).count()
    total_transactions = db.query(StockTransaction).count()
    total_stock = db.query(func.sum(Product.stock_quantity)).scalar() or 0
    
    # 최근 거래 내역 (거래처 정보 포함)
    recent_transactions = db.query(StockTransaction).join(Product).join(User).outerjoin(Supplier).order_by(StockTransaction.created_at.desc()).limit(10).all()
    
    # 카테고리별 재고
    categories = db.query(Product.category, func.sum(Product.stock_quantity)).group_by(Product.category).all()
    
    # 카테고리별 제품 목록 (트리 형태용)
    category_products = {}
    all_products = db.query(Product).all()

    for product in all_products:
        category = product.category or '미분류'

        if category not in category_products:
            category_products[category] = []
        category_products[category].append(product)
    
    
    # 모든 제품 목록 (차트용)
    products = db.query(Product).all()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total_products": total_products,
        "total_transactions": total_transactions,
        "total_stock": total_stock,
        "recent_transactions": recent_transactions,
        "categories": categories,
        "category_products": category_products,
        "products": products
    })

# 관리자 페이지
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    db = next(get_db())
    pending_users = db.query(User).filter(User.is_approved == False).all()
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "pending_users": pending_users
    })

# 감사 로그 페이지
@app.get("/audit-logs", response_class=HTMLResponse)
async def audit_logs_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    return templates.TemplateResponse("audit_logs.html", {
        "request": request,
        "user": user
    })


# 사용자 승인
@app.post("/admin/approve/{user_id}")
async def approve_user(user_id: int, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    current_user = get_current_user_from_cookie(access_token)
    if not current_user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    
    user.is_approved = True
    db.commit()
    return {"message": "사용자가 승인되었습니다"}

# 사용자 거부 (삭제)
@app.delete("/admin/reject/{user_id}")
async def reject_user(user_id: int, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    current_user = get_current_user_from_cookie(access_token)
    if not current_user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    
    # 관리자는 삭제할 수 없음
    if user.is_admin:
        raise HTTPException(status_code=400, detail="관리자는 삭제할 수 없습니다")
    
    db.delete(user)
    db.commit()
    return {"message": "사용자가 거부되었습니다"}

# 재고 관리 페이지
@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    db = next(get_db())
    products = db.query(Product).all()
    
    # 카테고리별 제품 그룹화 (카테고리 순서 고려)
    category_products = {}
    for product in products:
        category = product.category or '미분류'
        if category not in category_products:
            category_products[category] = []
        category_products[category].append(product)
    
    # 카테고리 순서 조회 (테이블이 존재할 때만)
    category_order_dict = {}
    try:
        if check_category_orders_table_exists():
            category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
            category_order_dict = {order.category_name: order.sort_order for order in category_orders}
    except Exception as e:
        print(f"카테고리 순서 조회 중 오류: {e}")
        category_order_dict = {}
    
    # 카테고리를 순서대로 정렬
    sorted_categories = sorted(category_products.keys(), 
                             key=lambda x: category_order_dict.get(x, 999))
    
    # 정렬된 카테고리 순서로 category_products 재구성
    ordered_category_products = {}
    for category in sorted_categories:
        ordered_category_products[category] = category_products[category]
    
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "products": products,
        "category_products": ordered_category_products
    })

# 제품 추가
@app.post("/inventory/add")
async def add_product(product: ProductCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    db_product = Product(
        name=product.name,
        description=product.description,
        price=product.price,
        stock_quantity=0,  # 초기 재고는 항상 0으로 설정
        safety_stock=product.safety_stock,
        safety_stock_level=product.safety_stock_level,
        category=product.category
    )
    db.add(db_product)
    
    # 새로운 카테고리인 경우 카테고리 순서에 추가
    if product.category and check_category_orders_table_exists():
        existing_category_order = db.query(CategoryOrder).filter(CategoryOrder.category_name == product.category).first()
        if not existing_category_order:
            # 새로운 카테고리 순서 생성 (가장 마지막 순서로)
            max_order = db.query(func.max(CategoryOrder.sort_order)).scalar() or 0
            new_category_order = CategoryOrder(
                category_name=product.category,
                sort_order=max_order + 1
            )
            db.add(new_category_order)
    
    db.commit()
    db.refresh(db_product)
    return {"message": "제품이 추가되었습니다", "product": db_product}

# 제품 목록 조회 API
@app.get("/api/products")
async def get_products(
    sort_by: str = "custom", 
    sort_order: str = "asc", 
    category: str = None,
    access_token: str = Cookie(None), 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        # 임시로 인증 없이 테스트
        pass
    
    query = db.query(Product)
    
    # 카테고리 필터
    if category and category != "all":
        if category == "uncategorized":
            query = query.filter(Product.category.is_(None))
        else:
            query = query.filter(Product.category == category)
    
    # 정렬
    if sort_by == "custom":
        # 사용자 정의 순서 (카테고리 순서 우선, 그 다음 제품 순서, 마지막으로 이름)
        products = query.all()
        
        # 카테고리 순서 조회 (테이블이 존재할 때만)
        category_order_dict = {}
        try:
            if check_category_orders_table_exists():
                category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
                category_order_dict = {order.category_name: order.sort_order for order in category_orders}
        except Exception as e:
            print(f"카테고리 순서 조회 중 오류: {e}")
            category_order_dict = {}
        
        # 카테고리 순서와 제품 순서로 정렬
        products = sorted(products, key=lambda p: (
            category_order_dict.get(p.category or '미분류', 999),
            p.sort_order or 0,
            p.name
        ))
    elif sort_by == "name":
        if sort_order == "desc":
            query = query.order_by(Product.name.desc())
        else:
            query = query.order_by(Product.name.asc())
        products = query.all()
    elif sort_by == "category":
        if sort_order == "desc":
            query = query.order_by(Product.category.desc().nulls_last())
        else:
            query = query.order_by(Product.category.asc().nulls_first())
        products = query.all()
    elif sort_by == "price":
        if sort_order == "desc":
            query = query.order_by(Product.price.desc())
        else:
            query = query.order_by(Product.price.asc())
        products = query.all()
    elif sort_by == "stock":
        if sort_order == "desc":
            query = query.order_by(Product.stock_quantity.desc())
        else:
            query = query.order_by(Product.stock_quantity.asc())
        products = query.all()
    elif sort_by == "safety_stock":
        if sort_order == "desc":
            query = query.order_by(Product.safety_stock.desc().nulls_last())
        else:
            query = query.order_by(Product.safety_stock.asc().nulls_first())
        products = query.all()
    else:
        # 기본 정렬도 카테고리 순서 적용
        products = query.all()
        
        # 카테고리 순서 조회 (테이블이 존재할 때만)
        category_order_dict = {}
        try:
            if check_category_orders_table_exists():
                category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
                category_order_dict = {order.category_name: order.sort_order for order in category_orders}
        except Exception as e:
            print(f"카테고리 순서 조회 중 오류: {e}")
            category_order_dict = {}
        
        # 카테고리 순서와 제품 순서로 정렬
        products = sorted(products, key=lambda p: (
            category_order_dict.get(p.category or '미분류', 999),
            p.sort_order or 0,
            p.name
        ))
    
    # SQLAlchemy 객체를 딕셔너리로 변환
    products_data = []
    for product in products:
        product_dict = {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "stock_quantity": product.stock_quantity,
            "safety_stock": product.safety_stock,
            "safety_stock_level": product.safety_stock_level,
            "category": product.category,
            "sort_order": product.sort_order,
            "created_at": product.created_at.isoformat() if product.created_at else None,
            "updated_at": product.updated_at.isoformat() if product.updated_at else None
        }
        products_data.append(product_dict)
    
    return {"products": products_data}

# 제품 순서 변경 API
@app.put("/api/products/reorder")
async def reorder_products(
    reorder_data: dict,
    access_token: str = Cookie(None), 
    db: Session = Depends(get_db)
):
    """제품들의 순서를 변경합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    try:
        # reorder_data 형식: {"product_orders": [{"id": 1, "sort_order": 1}, {"id": 2, "sort_order": 2}, ...]}
        product_orders = reorder_data.get("product_orders", [])
        
        if not product_orders:
            raise HTTPException(status_code=400, detail="제품 순서 정보가 필요합니다")
        
        # 각 제품의 순서 업데이트
        for item in product_orders:
            product_id = item.get("id")
            sort_order = item.get("sort_order")
            
            if not product_id or sort_order is None:
                continue
                
            product = db.query(Product).filter(Product.id == product_id).first()
            if product:
                product.sort_order = sort_order
        
        db.commit()
        
        return {"message": "제품 순서가 변경되었습니다", "updated_count": len(product_orders)}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"순서 변경 중 오류가 발생했습니다: {str(e)}")

# 카테고리 순서 변경 API
@app.put("/api/categories/reorder")
async def reorder_categories(
    reorder_data: dict,
    access_token: str = Cookie(None), 
    db: Session = Depends(get_db)
):
    """카테고리들의 순서를 변경합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    try:
        # category_orders 테이블이 존재하지 않으면 생성
        if not check_category_orders_table_exists():
            Base.metadata.create_all(bind=engine)
        
        # reorder_data 형식: {"category_orders": [{"category_name": "카테고리1", "sort_order": 1}, ...]}
        category_orders = reorder_data.get("category_orders", [])
        
        if not category_orders:
            raise HTTPException(status_code=400, detail="카테고리 순서 정보가 필요합니다")
        
        # 각 카테고리의 순서 업데이트
        updated_count = 0
        for item in category_orders:
            category_name = item.get("category_name")
            sort_order = item.get("sort_order")
            
            if not category_name or sort_order is None:
                continue
                
            # 기존 카테고리 순서 조회 또는 생성
            category_order = db.query(CategoryOrder).filter(CategoryOrder.category_name == category_name).first()
            if category_order:
                category_order.sort_order = sort_order
            else:
                # 새로운 카테고리 순서 생성
                # 만약 sort_order가 999라면 (새 카테고리 추가), 마지막 순서로 설정
                if sort_order == 999:
                    max_order = db.query(db.func.max(CategoryOrder.sort_order)).scalar() or 0
                    sort_order = max_order + 1
                
                category_order = CategoryOrder(
                    category_name=category_name,
                    sort_order=sort_order
                )
                db.add(category_order)
            
            updated_count += 1
        
        db.commit()
        
        return {"message": "카테고리 순서가 변경되었습니다", "updated_count": updated_count}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"카테고리 순서 변경 중 오류가 발생했습니다: {str(e)}")

# 카테고리 목록 조회 API
@app.get("/api/categories")
async def get_categories(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    """모든 카테고리 목록을 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    try:
        # 모든 제품의 카테고리 조회 (중복 제거)
        categories = db.query(Product.category).filter(Product.category.isnot(None)).distinct().all()
        category_list = [category[0] for category in categories if category[0]]
        
        # 카테고리 순서에 따라 정렬 (테이블이 존재할 때만)
        if check_category_orders_table_exists():
            category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
            order_dict = {order.category_name: order.sort_order for order in category_orders}
            
            # 순서가 있는 카테고리와 없는 카테고리 분리
            ordered_categories = []
            unordered_categories = []
            
            for category in category_list:
                if category in order_dict:
                    ordered_categories.append(category)
                else:
                    unordered_categories.append(category)
            
            # 순서대로 정렬 후 순서가 없는 카테고리 추가
            ordered_categories.sort(key=lambda x: order_dict[x])
            category_list = ordered_categories + sorted(unordered_categories)
        
        return category_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카테고리 목록 조회 중 오류가 발생했습니다: {str(e)}")

# 카테고리 순서 조회 API
@app.get("/api/categories/order")
async def get_category_orders(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    """카테고리 순서를 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    try:
        # 카테고리 순서 조회 (테이블이 존재할 때만)
        order_dict = {}
        if check_category_orders_table_exists():
            category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
            for order in category_orders:
                order_dict[order.category_name] = order.sort_order
        
        return {"category_orders": order_dict}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카테고리 순서 조회 중 오류가 발생했습니다: {str(e)}")


# 현재 사용자 정보 조회 API
@app.get("/api/user/me")
async def get_current_user_info(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "is_admin": user.is_admin,
        "is_approved": user.is_approved,
        "created_at": user.created_at
    }

# 제품 정보 조회 API
@app.get("/api/products/{product_id}")
async def get_product(product_id: int, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    return product

# 제품별 월별 소모량 및 예상 소모 개월 계산 API
@app.get("/api/products/{product_id}/consumption-analysis")
async def get_product_consumption_analysis(
    product_id: int, 
    months: int = 6,  # 분석할 개월 수 (기본 6개월)
    access_token: str = Cookie(None), 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    # 현재 시간에서 지정된 개월 수만큼 이전 날짜 계산
    current_time = get_seoul_time()
    start_date = current_time - timedelta(days=months * 30)  # 대략적인 개월 계산
    
    # 해당 기간 동안의 출고 거래 조회
    out_transactions = db.query(StockTransaction).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.transaction_type == "out",
        StockTransaction.created_at >= start_date
    ).order_by(StockTransaction.created_at.asc()).all()
    
    # 월별 소모량 계산
    monthly_consumption = {}
    for transaction in out_transactions:
        # 거래 날짜를 월 단위로 그룹화 (YYYY-MM 형식)
        month_key = transaction.created_at.strftime('%Y-%m')
        if month_key not in monthly_consumption:
            monthly_consumption[month_key] = 0
        monthly_consumption[month_key] += transaction.quantity
    
    # 월별 소모량 리스트 생성 (월 순서대로)
    monthly_data = []
    for month_key in sorted(monthly_consumption.keys()):
        monthly_data.append({
            "month": month_key,
            "consumption": monthly_consumption[month_key]
        })
    
    # 평균 월별 소모량 계산
    if monthly_data:
        total_consumption = sum(data["consumption"] for data in monthly_data)
        avg_monthly_consumption = total_consumption / len(monthly_data)
    else:
        avg_monthly_consumption = 0
    
    # 예상 소모 개월 계산
    if avg_monthly_consumption > 0:
        expected_months = product.stock_quantity / avg_monthly_consumption
    else:
        expected_months = float('inf')  # 소모량이 없으면 무한대
    
    return {
        "product_id": product_id,
        "product_name": product.name,
        "current_stock": product.stock_quantity,
        "analysis_period_months": months,
        "monthly_consumption_data": monthly_data,
        "average_monthly_consumption": round(avg_monthly_consumption, 2),
        "expected_consumption_months": round(expected_months, 1) if expected_months != float('inf') else None,
        "has_consumption_data": len(monthly_data) > 0
    }

# 제품 수정 API
@app.put("/api/products/{product_id}")
async def update_product(product_id: int, product_update: ProductUpdate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    db_product = db.query(Product).filter(Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    # 제품명 중복 확인 (자기 자신 제외)
    if product_update.name and product_update.name != db_product.name:
        existing_product = db.query(Product).filter(Product.name == product_update.name).first()
        if existing_product:
            raise HTTPException(status_code=400, detail="이미 존재하는 제품명입니다")
    
    # 카테고리 변경 확인
    old_category = db_product.category
    new_category = product_update.category if hasattr(product_update, 'category') and product_update.category else None
    
    # 필드 업데이트
    update_data = product_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)
    
    # 새로운 카테고리인 경우 카테고리 순서에 추가
    if new_category and new_category != old_category and check_category_orders_table_exists():
        existing_category_order = db.query(CategoryOrder).filter(CategoryOrder.category_name == new_category).first()
        if not existing_category_order:
            # 새로운 카테고리 순서 생성 (가장 마지막 순서로)
            max_order = db.query(func.max(CategoryOrder.sort_order)).scalar() or 0
            new_category_order = CategoryOrder(
                category_name=new_category,
                sort_order=max_order + 1
            )
            db.add(new_category_order)
    
    db.commit()
    db.refresh(db_product)
    
    return {"message": "제품이 수정되었습니다", "product": db_product}

# 입고 페이지
@app.get("/stock/in", response_class=HTMLResponse)
async def stock_in_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    db = next(get_db())
    
    # 카테고리 순서 조회 (테이블이 존재할 때만)
    category_order_dict = {}
    try:
        if check_category_orders_table_exists():
            category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
            category_order_dict = {order.category_name: order.sort_order for order in category_orders}
    except Exception as e:
        print(f"카테고리 순서 조회 중 오류: {e}")
        category_order_dict = {}
    
    # 제품을 카테고리 순서와 제품 순서로 정렬
    products = db.query(Product).all()
    sorted_products = sorted(products, key=lambda p: (
        category_order_dict.get(p.category or '미분류', 999),
        p.sort_order or 0,
        p.name
    ))
    
    return templates.TemplateResponse("stock_in.html", {
        "request": request,
        "products": sorted_products
    })

# 출고 페이지
@app.get("/stock/out", response_class=HTMLResponse)
async def stock_out_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    db = next(get_db())
    
    # 카테고리 순서 조회 (테이블이 존재할 때만)
    category_order_dict = {}
    try:
        if check_category_orders_table_exists():
            category_orders = db.query(CategoryOrder).order_by(CategoryOrder.sort_order.asc()).all()
            category_order_dict = {order.category_name: order.sort_order for order in category_orders}
    except Exception as e:
        print(f"카테고리 순서 조회 중 오류: {e}")
        category_order_dict = {}
    
    # 제품을 카테고리 순서와 제품 순서로 정렬
    products = db.query(Product).all()
    sorted_products = sorted(products, key=lambda p: (
        category_order_dict.get(p.category or '미분류', 999),
        p.sort_order or 0,
        p.name
    ))
    
    return templates.TemplateResponse("stock_out.html", {
        "request": request,
        "products": sorted_products
    })

# 입고 처리
@app.post("/stock/in")
async def process_stock_in(transaction: StockTransactionCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    product = db.query(Product).filter(Product.id == transaction.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    # 재고 수량 증가
    product.stock_quantity += transaction.quantity
    
    # 입고 거래 기록 (서울 시간대 사용)
    current_time = get_seoul_time()
    transaction_time = transaction.transaction_date if transaction.transaction_date else current_time
    stock_transaction = StockTransaction(
        product_id=transaction.product_id,
        user_id=user.id,
        supplier_id=transaction.supplier_id,
        transaction_type="in",
        quantity=transaction.quantity,
        lot_number=transaction.lot_number,
        location=transaction.location,
        notes=transaction.notes,
        created_at=transaction_time
    )
    db.add(stock_transaction)
    db.flush()  # ID를 얻기 위해 flush
    
    # 선납금 자동 차감 (입고 시)
    if transaction.supplier_id:
        total_amount = product.price * transaction.quantity
        auto_deduct_prepayment(db, transaction.supplier_id, total_amount, stock_transaction.id, user.id)
    
    db.commit()
    
    return {"message": "입고가 완료되었습니다"}

# 다중 제품 입고 처리
@app.post("/stock/in/bulk")
async def process_bulk_stock_in(bulk_data: BulkStockInCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    if not bulk_data.items:
        raise HTTPException(status_code=400, detail="입고할 제품이 없습니다")
    
    # 모든 제품의 존재 확인 (중복 제거)
    product_ids = list(set([item.product_id for item in bulk_data.items]))  # 중복 제거
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="일부 제품을 찾을 수 없습니다")
    
    # 제품별 입고 수량 집계
    product_in_totals = {}
    for item in bulk_data.items:
        if item.product_id not in product_in_totals:
            product_in_totals[item.product_id] = 0
        product_in_totals[item.product_id] += item.quantity
    
    # LOT 번호 중복 체크 (동일한 제품에서 같은 LOT 번호가 여러 번 나타나는지 확인)
    lot_duplicates = {}
    for item in bulk_data.items:
        if item.lot_number:
            lot_key = (item.product_id, item.lot_number)
            if lot_key not in lot_duplicates:
                lot_duplicates[lot_key] = []
            lot_duplicates[lot_key].append(item.quantity)
    
    # 중복 LOT 번호가 있는 경우 경고 (입고는 허용하되 경고 메시지)
    duplicate_lots = []
    for (product_id, lot_number), quantities in lot_duplicates.items():
        if len(quantities) > 1:
            product = next(p for p in products if p.id == product_id)
            total_quantity = sum(quantities)
            duplicate_lots.append(f"제품 '{product.name}' LOT {lot_number}: {len(quantities)}번 입력, 총 {total_quantity}개")
    
    # 모든 검증이 통과하면 입고 처리
    transactions = []
    current_time = get_seoul_time()
    transaction_time = bulk_data.transaction_date if bulk_data.transaction_date else current_time
    
    # 제품별 총 입고량을 먼저 계산하여 재고 업데이트
    for product_id, total_in_quantity in product_in_totals.items():
        product = next(p for p in products if p.id == product_id)
        product.stock_quantity += total_in_quantity
    
    # 각 아이템별로 거래 기록 생성
    for item in bulk_data.items:
        # 입고 거래 기록 (서울 시간대 사용)
        stock_transaction = StockTransaction(
            product_id=item.product_id,
            user_id=user.id,
            supplier_id=bulk_data.supplier_id,
            transaction_type="in",
            quantity=item.quantity,
            lot_number=item.lot_number,
            location=None,
            notes=bulk_data.notes,
            created_at=transaction_time
        )
        transactions.append(stock_transaction)
        db.add(stock_transaction)
    
    db.flush()  # ID를 얻기 위해 flush
    
    # 선납금 자동 차감 (다중 입고 시)
    if bulk_data.supplier_id:
        total_amount = 0
        for item in bulk_data.items:
            product = next(p for p in products if p.id == item.product_id)
            total_amount += product.price * item.quantity
        
        # 각 거래에 대해 선납금 차감
        for transaction in transactions:
            product = next(p for p in products if p.id == transaction.product_id)
            item_amount = product.price * transaction.quantity
            auto_deduct_prepayment(db, bulk_data.supplier_id, item_amount, transaction.id, user.id)
    
    db.commit()
    
    # 응답 메시지 구성
    message = f"{len(bulk_data.items)}개 제품의 입고가 완료되었습니다"
    if duplicate_lots:
        message += f"\n\n주의: 다음 LOT 번호가 중복 입력되었습니다:\n" + "\n".join(duplicate_lots)
    
    return {
        "message": message,
        "processed_items": len(bulk_data.items),
        "duplicate_lots": duplicate_lots if duplicate_lots else None
    }

# 출고 처리
@app.post("/stock/out")
async def process_stock_out(transaction: StockTransactionCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    product = db.query(Product).filter(Product.id == transaction.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    # 수량 유효성 검사
    if transaction.quantity <= 0:
        raise HTTPException(status_code=400, detail="출고 수량은 1 이상이어야 합니다.")
    
    # 전체 재고 확인
    if product.stock_quantity < transaction.quantity:
        raise HTTPException(status_code=400, detail=f"재고가 부족합니다. (현재 재고: {product.stock_quantity}개, 요청 수량: {transaction.quantity}개)")
    
    # LOT별 재고 확인 (LOT 번호가 있는 경우)
    if transaction.lot_number:
        # 해당 LOT의 입고 수량 계산
        in_quantity = db.query(func.sum(StockTransaction.quantity)).filter(
            StockTransaction.product_id == transaction.product_id,
            StockTransaction.lot_number == transaction.lot_number,
            StockTransaction.transaction_type == "in"
        ).scalar() or 0
        
        # 해당 LOT의 출고 수량 계산
        out_quantity = db.query(func.sum(StockTransaction.quantity)).filter(
            StockTransaction.product_id == transaction.product_id,
            StockTransaction.lot_number == transaction.lot_number,
            StockTransaction.transaction_type == "out"
        ).scalar() or 0
        
        # LOT별 현재 재고
        lot_current_stock = in_quantity - out_quantity
        
        # LOT 재고가 0 이하인 경우
        if lot_current_stock <= 0:
            raise HTTPException(
                status_code=400, 
                detail=f"LOT {transaction.lot_number}의 재고가 없습니다. (LOT 재고: {lot_current_stock}개)"
            )
        
        # 요청 수량이 LOT 재고를 초과하는 경우
        if lot_current_stock < transaction.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"LOT {transaction.lot_number}의 재고가 부족합니다. (LOT 재고: {lot_current_stock}개, 요청 수량: {transaction.quantity}개, 부족 수량: {transaction.quantity - lot_current_stock}개)"
            )
    
    # 재고 수량 감소
    product.stock_quantity -= transaction.quantity
    
    # 출고 거래 기록 (서울 시간대 사용)
    current_time = get_seoul_time()
    transaction_time = transaction.transaction_date if transaction.transaction_date else current_time
    stock_transaction = StockTransaction(
        product_id=transaction.product_id,
        user_id=user.id,
        supplier_id=transaction.supplier_id,
        transaction_type="out",
        quantity=transaction.quantity,
        lot_number=transaction.lot_number,
        location=transaction.location,
        notes=transaction.notes,
        created_at=transaction_time
    )
    db.add(stock_transaction)
    db.flush()  # ID를 얻기 위해 flush
    
    # 선납금 자동 차감 (출고 시 - 고객으로부터 선납금을 받은 경우)
    if transaction.supplier_id:
        total_amount = product.price * transaction.quantity
        auto_deduct_prepayment(db, transaction.supplier_id, total_amount, stock_transaction.id, user.id)
    
    db.commit()
    
    return {"message": "출고가 완료되었습니다"}

# 다중 제품 출고 처리
@app.post("/stock/out/bulk")
async def process_bulk_stock_out(bulk_data: BulkStockOutCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    if not bulk_data.items:
        raise HTTPException(status_code=400, detail="출고할 제품이 없습니다")
    
    # 수량 유효성 검사
    for item in bulk_data.items:
        if item.quantity <= 0:
            raise HTTPException(status_code=400, detail=f"출고 수량은 1 이상이어야 합니다. (제품 ID: {item.product_id})")
    
    # 모든 제품의 재고 확인 (중복 제거)
    product_ids = list(set([item.product_id for item in bulk_data.items]))  # 중복 제거
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="일부 제품을 찾을 수 없습니다")
    
    # 제품별 출고 수량 집계 (LOT 무관)
    product_out_totals = {}
    for item in bulk_data.items:
        if item.product_id not in product_out_totals:
            product_out_totals[item.product_id] = 0
        product_out_totals[item.product_id] += item.quantity
    
    # 전체 재고 확인 (제품별 총 출고량 vs 현재 재고)
    for product_id, total_out_quantity in product_out_totals.items():
        product = next(p for p in products if p.id == product_id)
        if product.stock_quantity < total_out_quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"제품 '{product.name}'의 재고가 부족합니다. (현재 재고: {product.stock_quantity}개, 총 출고 수량: {total_out_quantity}개)"
            )
    
    # LOT별 재고 확인 및 LOT별 출고량 집계
    lot_out_totals = {}  # (product_id, lot_number) -> total_quantity
    for item in bulk_data.items:
        if item.lot_number:
            lot_key = (item.product_id, item.lot_number)
            if lot_key not in lot_out_totals:
                lot_out_totals[lot_key] = 0
            lot_out_totals[lot_key] += item.quantity
    
    # 각 LOT별 재고 확인
    for (product_id, lot_number), total_lot_out in lot_out_totals.items():
        # 해당 LOT의 입고 수량 계산
        in_quantity = db.query(func.sum(StockTransaction.quantity)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.lot_number == lot_number,
            StockTransaction.transaction_type == "in"
        ).scalar() or 0
        
        # 해당 LOT의 출고 수량 계산
        out_quantity = db.query(func.sum(StockTransaction.quantity)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.lot_number == lot_number,
            StockTransaction.transaction_type == "out"
        ).scalar() or 0
        
        # LOT별 현재 재고
        lot_current_stock = in_quantity - out_quantity
        
        # LOT 재고가 0 이하인 경우
        if lot_current_stock <= 0:
            product = next(p for p in products if p.id == product_id)
            raise HTTPException(
                status_code=400, 
                detail=f"제품 '{product.name}' LOT {lot_number}의 재고가 없습니다. (LOT 재고: {lot_current_stock}개)"
            )
        
        # 요청 수량이 LOT 재고를 초과하는 경우
        if lot_current_stock < total_lot_out:
            product = next(p for p in products if p.id == product_id)
            raise HTTPException(
                status_code=400, 
                detail=f"제품 '{product.name}' LOT {lot_number}의 재고가 부족합니다. (LOT 재고: {lot_current_stock}개, 총 출고 수량: {total_lot_out}개, 부족 수량: {total_lot_out - lot_current_stock}개)"
            )
    
    # 모든 검증이 통과하면 출고 처리
    transactions = []
    current_time = get_seoul_time()
    transaction_time = bulk_data.transaction_date if bulk_data.transaction_date else current_time
    
    # 제품별 총 출고량을 먼저 계산하여 재고 업데이트
    for product_id, total_out_quantity in product_out_totals.items():
        product = next(p for p in products if p.id == product_id)
        product.stock_quantity -= total_out_quantity
    
    # 각 아이템별로 거래 기록 생성
    for item in bulk_data.items:
        # 출고 거래 기록 (서울 시간대 사용)
        stock_transaction = StockTransaction(
            product_id=item.product_id,
            user_id=user.id,
            supplier_id=bulk_data.supplier_id,
            transaction_type="out",
            quantity=item.quantity,
            lot_number=item.lot_number,
            location=None,
            notes=bulk_data.notes,
            created_at=transaction_time
        )
        transactions.append(stock_transaction)
        db.add(stock_transaction)
    
    db.flush()  # ID를 얻기 위해 flush
    
    # 선납금 자동 차감 (다중 출고 시)
    if bulk_data.supplier_id:
        # 각 거래에 대해 선납금 차감
        for transaction in transactions:
            product = next(p for p in products if p.id == transaction.product_id)
            item_amount = product.price * transaction.quantity
            auto_deduct_prepayment(db, bulk_data.supplier_id, item_amount, transaction.id, user.id)
    
    db.commit()
    
    return {
        "message": f"{len(bulk_data.items)}개 제품의 출고가 완료되었습니다",
        "processed_items": len(bulk_data.items)
    }

# 제품별 LOT 목록 조회 API
@app.get("/api/products/{product_id}/lots")
async def get_product_lots(product_id: int, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 제품 존재 확인
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    # 입고 거래에서 LOT별 재고 계산
    lot_stocks = {}
    
    # 입고 거래 조회
    in_transactions = db.query(StockTransaction).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.transaction_type == "in",
        StockTransaction.lot_number.isnot(None)
    ).all()
    
    # 출고 거래 조회
    out_transactions = db.query(StockTransaction).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.transaction_type == "out",
        StockTransaction.lot_number.isnot(None)
    ).all()
    
    # LOT별 입고 수량 계산
    for transaction in in_transactions:
        lot_number = transaction.lot_number
        if lot_number not in lot_stocks:
            lot_stocks[lot_number] = 0
        lot_stocks[lot_number] += transaction.quantity
    
    # LOT별 출고 수량 계산
    for transaction in out_transactions:
        lot_number = transaction.lot_number
        if lot_number in lot_stocks:
            lot_stocks[lot_number] -= transaction.quantity
    
    # 재고가 있는 LOT만 반환
    available_lots = []
    for lot_number, quantity in lot_stocks.items():
        if quantity > 0:
            available_lots.append({
                "lot_number": lot_number,
                "quantity": quantity
            })
    
    return available_lots

# 거래처 관리 페이지
@app.get("/suppliers", response_class=HTMLResponse)
async def suppliers_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("suppliers.html", {
        "request": request,
        "user": user
    })

# 장부 페이지
@app.get("/ledger", response_class=HTMLResponse)
async def ledger_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("ledger.html", {
        "request": request,
        "user": user
    })

# 거래처 목록 조회 API
@app.get("/api/suppliers")
async def get_suppliers(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    try:
        # 테이블 존재 여부 확인
        db.execute(text("SELECT 1 FROM suppliers LIMIT 1"))
        suppliers = db.query(Supplier).order_by(Supplier.supplier_type.asc(), Supplier.sort_order.asc(), Supplier.name.asc()).all()
        return {
            "suppliers": [
                {
                    "id": supplier.id,
                    "name": supplier.name,
                    "contact_person": supplier.contact_person,
                    "phone": supplier.phone,
                    "email": supplier.email,
                    "address": supplier.address,
                    "supplier_type": supplier.supplier_type,
                    "sort_order": supplier.sort_order,
                    "is_active": supplier.is_active,
                    "created_at": supplier.created_at.isoformat() if supplier.created_at else None
                }
                for supplier in suppliers
            ]
        }
    except Exception as e:
        print(f"DEBUG: suppliers 테이블 조회 중 오류: {e}")
        # 테이블이 없으면 생성 시도
        try:
            Base.metadata.create_all(bind=engine)
            print("suppliers 테이블을 생성했습니다.")
            return {"suppliers": []}
        except Exception as create_error:
            print(f"DEBUG: 테이블 생성 중 오류: {create_error}")
            raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

# 거래처 추가 API
@app.post("/api/suppliers")
async def create_supplier(supplier: SupplierCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 거래처명 중복 확인
    existing_supplier = db.query(Supplier).filter(Supplier.name == supplier.name).first()
    if existing_supplier:
        raise HTTPException(status_code=400, detail="이미 존재하는 거래처명입니다")
    
    db_supplier = Supplier(
        name=supplier.name,
        contact_person=supplier.contact_person,
        phone=supplier.phone,
        email=supplier.email,
        address=supplier.address,
        supplier_type=supplier.supplier_type
    )
    db.add(db_supplier)
    db.commit()
    db.refresh(db_supplier)
    
    return {"message": "거래처가 추가되었습니다", "supplier": db_supplier}

# 거래처 정렬 순서 업데이트 API (더 구체적인 경로를 먼저 정의)
@app.put("/api/suppliers/update-sort-order")
async def update_supplier_sort_order(request: Request, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    try:
        # Request body에서 JSON 데이터 가져오기
        body = await request.json()
        
        # body는 {"sort_orders": {"supplier_id": sort_order}} 형태
        sort_orders = body.get("sort_orders", {})
        
        for supplier_id, sort_order in sort_orders.items():
            db_supplier = db.query(Supplier).filter(Supplier.id == int(supplier_id)).first()
            if db_supplier:
                db_supplier.sort_order = int(sort_order)
        
        db.commit()
        return {"message": "거래처 정렬 순서가 업데이트되었습니다"}
    
    except Exception as e:
        print(f"Error in sort order update: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=400, detail=f"정렬 순서 업데이트 중 오류가 발생했습니다: {str(e)}")

# 거래처 수정 API
@app.put("/api/suppliers/{supplier_id}")
async def update_supplier(supplier_id: int, supplier_update: SupplierUpdate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    db_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다")
    
    # 거래처명 중복 확인 (자기 자신 제외)
    if supplier_update.name and supplier_update.name != db_supplier.name:
        existing_supplier = db.query(Supplier).filter(Supplier.name == supplier_update.name).first()
        if existing_supplier:
            raise HTTPException(status_code=400, detail="이미 존재하는 거래처명입니다")
    
    # 필드 업데이트
    update_data = supplier_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_supplier, field, value)
    
    db.commit()
    db.refresh(db_supplier)
    
    return {"message": "거래처가 수정되었습니다", "supplier": db_supplier}

# 거래처 삭제 API
@app.delete("/api/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: int, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    db_supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not db_supplier:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다")
    
    # 거래 내역이 있는지 확인
    transaction_count = db.query(StockTransaction).filter(StockTransaction.supplier_id == supplier_id).count()
    if transaction_count > 0:
        raise HTTPException(status_code=400, detail="거래 내역이 있는 거래처는 삭제할 수 없습니다. 비활성화를 사용하세요.")
    
    db.delete(db_supplier)
    db.commit()
    
    return {"message": "거래처가 삭제되었습니다"}

# 재고 수량 동기화 API (거래 내역 기반으로 재계산)
@app.post("/api/admin/sync-stock-quantities")
async def sync_stock_quantities(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    try:
        # 모든 제품 조회
        products = db.query(Product).all()
        sync_results = []
        
        for product in products:
            # 해당 제품의 모든 거래 내역 조회
            transactions = db.query(StockTransaction).filter(
                StockTransaction.product_id == product.id
            ).all()
            
            # 거래 내역 기반으로 재고 수량 계산
            calculated_stock = 0
            for transaction in transactions:
                if transaction.transaction_type == "in":
                    calculated_stock += transaction.quantity
                elif transaction.transaction_type == "out":
                    calculated_stock -= transaction.quantity
            
            # 기존 재고와 계산된 재고 비교
            old_stock = product.stock_quantity
            product.stock_quantity = calculated_stock
            
            sync_results.append({
                "product_id": product.id,
                "product_name": product.name,
                "old_stock": old_stock,
                "new_stock": calculated_stock,
                "difference": calculated_stock - old_stock
            })
        
        # 데이터베이스 커밋
        db.commit()
        
        return {
            "message": f"{len(products)}개 제품의 재고 수량이 동기화되었습니다",
            "sync_results": sync_results
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"재고 동기화 중 오류가 발생했습니다: {str(e)}")

# 안전 재고 설정 API
@app.put("/api/products/{product_id}/safety-stock")
async def update_safety_stock(
    product_id: int, 
    safety_stock_data: dict, 
    access_token: str = Cookie(None), 
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
    # 안전재고 수량만 설정 (단계는 변경하지 않음)
    product.safety_stock = safety_stock_data.get('safety_stock', 0)
    
    db.commit()
    db.refresh(product)
    
    return {"message": "안전 재고가 설정되었습니다", "product": product}

# 안전 재고 알림 조회 API
@app.get("/api/safety-stock-alerts")
async def get_safety_stock_alerts(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 3단계 안전재고 알림 시스템
    critical_products = []  # 응급: 재고가 안전재고 이하
    warning_products = []   # 주의: 재고가 안전재고의 1.5배 이하
    good_products = []      # 양호: 재고가 충분
    
    all_products = db.query(Product).filter(Product.safety_stock > 0).all()
    
    for product in all_products:
        if product.stock_quantity <= product.safety_stock:
            # 응급 단계
            critical_products.append(product)
        elif product.stock_quantity <= product.safety_stock * 1.5:
            # 주의 단계
            warning_products.append(product)
        else:
            # 양호 단계
            good_products.append(product)
    
    return {
        "critical_products": critical_products,
        "warning_products": warning_products,
        "good_products": good_products,
        "total_alerts": len(critical_products) + len(warning_products)
    }

# 필터링된 거래 내역 조회 API
@app.get("/api/transactions/filtered")
async def get_filtered_transactions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    supplier_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    product_id: Optional[int] = None,
    product_search: Optional[str] = None,
    category: Optional[str] = None,
    lot_number: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 기본 쿼리 (관계 포함)
    query = db.query(StockTransaction).join(Product).join(User).outerjoin(Supplier)
    
    # 날짜 필터 (서울 시간대 사용)
    if date_from:
        try:
            from_date = parse_date_with_timezone(date_from)
            query = query.filter(StockTransaction.created_at >= from_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    if date_to:
        try:
            to_date = parse_date_with_timezone(date_to)
            # 종료일은 23:59:59까지 포함
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(StockTransaction.created_at <= to_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # 거래처 필터
    if supplier_id:
        query = query.filter(StockTransaction.supplier_id == supplier_id)
    
    # 거래 유형 필터
    if transaction_type:
        query = query.filter(StockTransaction.transaction_type == transaction_type)
    
    # 제품 ID 필터
    if product_id:
        query = query.filter(StockTransaction.product_id == product_id)
    
    # 제품명 검색 필터
    if product_search:
        query = query.filter(Product.name.contains(product_search))
    
    # 카테고리 필터
    if category and category != "all":
        if category == "uncategorized":
            query = query.filter(Product.category.is_(None))
        else:
            query = query.filter(Product.category == category)
    
    # 라트 번호 검색 필터
    if lot_number:
        query = query.filter(StockTransaction.lot_number.contains(lot_number))
    
    # 전체 개수 계산
    total_transactions = query.count()
    total_pages = (total_transactions + per_page - 1) // per_page
    
    # 페이지네이션 적용 (관계 미리 로드)
    offset = (page - 1) * per_page
    transactions = query.options(
        joinedload(StockTransaction.product),
        joinedload(StockTransaction.supplier),
        joinedload(StockTransaction.user)
    ).order_by(StockTransaction.created_at.desc()).offset(offset).limit(per_page).all()
    
    # 통계 계산
    stats_query = db.query(StockTransaction)
    
    # 동일한 필터 적용 (서울 시간대 사용)
    if date_from:
        from_date = parse_date_with_timezone(date_from)
        stats_query = stats_query.filter(StockTransaction.created_at >= from_date)
    if date_to:
        to_date = parse_date_with_timezone(date_to)
        to_date = to_date.replace(hour=23, minute=59, second=59)
        stats_query = stats_query.filter(StockTransaction.created_at <= to_date)
    if supplier_id:
        stats_query = stats_query.filter(StockTransaction.supplier_id == supplier_id)
    if transaction_type:
        stats_query = stats_query.filter(StockTransaction.transaction_type == transaction_type)
    if product_id:
        stats_query = stats_query.filter(StockTransaction.product_id == product_id)
    if product_search:
        stats_query = stats_query.join(Product).filter(Product.name.contains(product_search))
    if category and category != "all":
        if not product_search:  # 이미 join이 되어있지 않은 경우
            stats_query = stats_query.join(Product)
        if category == "uncategorized":
            stats_query = stats_query.filter(Product.category.is_(None))
        else:
            stats_query = stats_query.filter(Product.category == category)
    if lot_number:
        stats_query = stats_query.filter(StockTransaction.lot_number.contains(lot_number))
    
    # 입고/출고 수량 통계
    in_quantity = stats_query.filter(StockTransaction.transaction_type == "in").with_entities(func.sum(StockTransaction.quantity)).scalar() or 0
    out_quantity = stats_query.filter(StockTransaction.transaction_type == "out").with_entities(func.sum(StockTransaction.quantity)).scalar() or 0
    
    # 거래처 수 계산
    total_suppliers = stats_query.filter(StockTransaction.supplier_id.isnot(None)).with_entities(StockTransaction.supplier_id).distinct().count()
    
    return {
        "recent_transactions": transactions,
        "total_transactions": total_transactions,
        "total_pages": total_pages,
        "current_page": page,
        "total_in_quantity": in_quantity,
        "total_out_quantity": out_quantity,
        "total_suppliers": total_suppliers
    }

# 거래 내역 삭제 API
@app.delete("/api/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: int, 
    request: Request,
    access_token: str = Cookie(None), 
    db: Session = Depends(get_db)
):
    print(f"DEBUG: 거래 내역 삭제 요청 - ID: {transaction_id}")
    
    user = get_current_user_from_cookie(access_token)
    if not user:
        print("DEBUG: 인증 실패")
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not user.is_admin:
        print(f"DEBUG: 관리자 권한 없음 - 사용자: {user.username}")
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    print(f"DEBUG: 관리자 인증 성공 - 사용자: {user.username}")
    
    # 거래 내역 조회
    transaction = db.query(StockTransaction).filter(StockTransaction.id == transaction_id).first()
    if not transaction:
        print(f"DEBUG: 거래 내역을 찾을 수 없음 - ID: {transaction_id}")
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다")
    
    print(f"DEBUG: 거래 내역 발견 - ID: {transaction.id}, 제품: {transaction.product_id}, 유형: {transaction.transaction_type}, 수량: {transaction.quantity}")
    
    # 제품 정보 조회
    product = db.query(Product).filter(Product.id == transaction.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="관련 제품을 찾을 수 없습니다")
    
    # 삭제 전 정보 저장 (로그용)
    transaction_details = {
        "product_name": product.name,
        "product_id": transaction.product_id,
        "transaction_type": transaction.transaction_type,
        "quantity": transaction.quantity,
        "lot_number": transaction.lot_number,
        "supplier_name": transaction.supplier.name if transaction.supplier else None,
        "supplier_id": transaction.supplier_id,
        "original_user": transaction.user.full_name if transaction.user else None,
        "original_user_id": transaction.user_id,
        "notes": transaction.notes,
        "created_at": transaction.created_at.isoformat() if transaction.created_at else None,
        "stock_before": product.stock_quantity
    }
    
    # 재고 수량 복원 (삭제 시 반대 작업 수행)
    if transaction.transaction_type == "in":
        # 입고 거래 삭제 시 재고 감소
        if product.stock_quantity < transaction.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"재고가 부족하여 삭제할 수 없습니다. (현재 재고: {product.stock_quantity}개, 삭제할 수량: {transaction.quantity}개)"
            )
        product.stock_quantity -= transaction.quantity
    else:
        # 출고 거래 삭제 시 재고 증가
        product.stock_quantity += transaction.quantity
    
    # 삭제 후 재고 정보 추가
    transaction_details["stock_after"] = product.stock_quantity
    
    # 거래 내역 삭제
    db.delete(transaction)
    
    # 감사 로그 기록 (테이블이 있을 때만)
    try:
        import json
        audit_log = AuditLog(
            user_id=user.id,
            action="DELETE_TRANSACTION",
            target_type="StockTransaction",
            target_id=transaction_id,
            details=json.dumps(transaction_details, ensure_ascii=False),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            created_at=get_seoul_time()  # 서울 시간으로 명시적 설정
        )
        db.add(audit_log)
        print(f"DEBUG: 감사 로그 기록 완료 - 관리자: {user.username}")
    except Exception as e:
        print(f"DEBUG: 감사 로그 기록 실패 (테이블 없음): {e}")
        # 감사 로그 기록 실패해도 거래 내역 삭제는 계속 진행
    
    db.commit()
    
    print(f"DEBUG: 거래 내역 삭제 완료 - ID: {transaction_id}, 관리자: {user.username}")
    
    return {"message": "거래 내역이 삭제되었습니다"}

# 거래 내역 상세 조회 API
@app.get("/api/transactions/{transaction_id}")
async def get_transaction_detail(
    transaction_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 거래 내역 조회
    transaction = db.query(StockTransaction).options(
        joinedload(StockTransaction.product),
        joinedload(StockTransaction.supplier),
        joinedload(StockTransaction.user)
    ).filter(StockTransaction.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다")
    
    return transaction

# 거래 내역 수량 수정 API
@app.put("/api/transactions/{transaction_id}/quantity")
async def update_transaction_quantity(
    transaction_id: int,
    update_data: StockTransactionQuantityUpdate,
    request: Request,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    # 거래 내역 조회
    transaction = db.query(StockTransaction).options(
        joinedload(StockTransaction.product)
    ).filter(StockTransaction.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="거래 내역을 찾을 수 없습니다")
    
    # 제품 조회
    product = transaction.product
    if not product:
        raise HTTPException(status_code=404, detail="제품 정보를 찾을 수 없습니다")
    
    # 기존 수량과 새 수량
    old_quantity = transaction.quantity
    new_quantity = update_data.new_quantity
    
    if new_quantity <= 0:
        raise HTTPException(status_code=400, detail="수량은 1 이상이어야 합니다")
    
    # 수량 차이 계산
    quantity_diff = new_quantity - old_quantity
    
    # 재고 조정 (입고는 +, 출고는 -)
    if transaction.transaction_type == "in":
        # 입고 수량 수정: 차이만큼 재고 조정
        product.stock_quantity += quantity_diff
    else:
        # 출고 수량 수정: 차이만큼 재고 조정 (차이가 음수면 재고 증가, 양수면 재고 감소)
        product.stock_quantity -= quantity_diff
        
        # 출고 수량이 증가하는 경우 재고 부족 확인
        if quantity_diff > 0 and product.stock_quantity < 0:
            raise HTTPException(
                status_code=400, 
                detail=f"재고가 부족합니다. (현재 재고: {product.stock_quantity + quantity_diff}개, 추가 출고 요청: {quantity_diff}개)"
            )
    
    # 거래 내역 수량 업데이트
    transaction.quantity = new_quantity
    
    # 감사 로그 기록
    try:
        import json
        transaction_details = {
            "product_id": transaction.product_id,
            "product_name": product.name,
            "transaction_type": transaction.transaction_type,
            "old_quantity": old_quantity,
            "new_quantity": new_quantity,
            "quantity_diff": quantity_diff,
            "reason": update_data.reason,
            "supplier_id": transaction.supplier_id,
            "lot_number": transaction.lot_number
        }
        
        audit_log = AuditLog(
            user_id=user.id,
            action="수량 수정",
            target_type="StockTransaction",
            target_id=transaction_id,
            details=json.dumps(transaction_details, ensure_ascii=False),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            created_at=get_seoul_time()
        )
        db.add(audit_log)
    except Exception as e:
        print(f"감사 로그 기록 실패: {e}")
        # 감사 로그 기록 실패해도 수정은 계속 진행
    
    db.commit()
    
    return {"message": "수량이 성공적으로 수정되었습니다"}

# audit_logs 테이블 생성 API
@app.post("/api/debug/create-audit-logs-table")
async def create_audit_logs_table(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    """audit_logs 테이블을 수동으로 생성합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    try:
        # audit_logs 테이블을 직접 SQL로 생성
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action VARCHAR(50) NOT NULL,
            target_type VARCHAR(50) NOT NULL,
            target_id INTEGER,
            details TEXT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
        db.execute(create_table_sql)
        db.commit()
        
        # 인덱스 생성
        db.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs (id)")
        db.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id)")
        db.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at)")
        db.commit()
        
        return {"message": "audit_logs 테이블이 성공적으로 생성되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"테이블 생성 실패: {str(e)}")

# 거래 내역 디버깅 API (임시)
@app.get("/api/debug/transactions")
async def debug_transactions(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    """거래 내역 디버깅 정보를 반환합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    transactions = db.query(StockTransaction).join(User).all()
    result = []
    for t in transactions:
        result.append({
            "id": t.id,
            "product_id": t.product_id,
            "user_id": t.user_id,
            "user_name": t.user.full_name if t.user else None,
            "transaction_type": t.transaction_type,
            "quantity": t.quantity,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    return {"transactions": result, "count": len(result)}

# 감사 로그 조회 API
@app.get("/api/audit-logs")
async def get_audit_logs(
    page: int = 1,
    per_page: int = 20,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """감사 로그를 조회합니다. (관리자만 접근 가능)"""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 관리자 권한 확인
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")
    
    try:
        # 감사 로그 조회
        query = db.query(AuditLog).join(User).order_by(AuditLog.created_at.desc())
        
        # 전체 개수 계산
        total_logs = query.count()
        total_pages = (total_logs + per_page - 1) // per_page
        
        # 페이지네이션 적용
        offset = (page - 1) * per_page
        logs = query.offset(offset).limit(per_page).all()
        
        result = []
        for log in logs:
            # 기존 데이터는 UTC로 저장되어 있을 수 있으므로 서울 시간대로 변환
            formatted_time = None
            if log.created_at:
                if log.created_at.tzinfo is None:
                    # naive datetime인 경우 UTC로 가정하고 서울 시간대로 변환
                    utc_time = pytz.UTC.localize(log.created_at)
                    formatted_time = utc_time.astimezone(SEOUL_TZ).isoformat()
                else:
                    # 이미 시간대 정보가 있는 경우 서울 시간대로 변환
                    formatted_time = log.created_at.astimezone(SEOUL_TZ).isoformat()
            
            result.append({
                "id": log.id,
                "user_name": log.user.full_name,
                "user_username": log.user.username,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "created_at": formatted_time
            })
        
        return {
            "logs": result,
            "total_logs": total_logs,
            "total_pages": total_pages,
            "current_page": page
        }
    except Exception as e:
        return {
            "logs": [],
            "total_logs": 0,
            "total_pages": 0,
            "current_page": page,
            "error": f"감사 로그 조회 실패: {str(e)}",
            "message": "audit_logs 테이블이 아직 생성되지 않았습니다."
        }

# 시간대 디버깅 API
@app.get("/api/debug/timezone")
async def debug_timezone():
    """시간대 디버깅 정보를 반환합니다."""
    import time
    from datetime import datetime
    
    utc_now = datetime.utcnow()
    seoul_now = get_seoul_time()
    local_now = datetime.now()
    
    return {
        "utc_time": utc_now.strftime('%Y-%m-%d %H:%M:%S'),
        "seoul_time": seoul_now.strftime('%Y-%m-%d %H:%M:%S'),
        "local_time": local_now.strftime('%Y-%m-%d %H:%M:%S'),
        "timezone_offset": time.timezone,
        "timezone_name": time.tzname,
        "environment_tz": os.environ.get('TZ', 'Not set')
    }

# 거래 내역 엑셀 다운로드 API
@app.get("/api/transactions/export")
async def export_transactions(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    supplier_id: Optional[int] = None,
    transaction_type: Optional[str] = None,
    product_id: Optional[int] = None,
    product_search: Optional[str] = None,
    category: Optional[str] = None,
    lot_number: Optional[str] = None,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 기본 쿼리 (관계 포함)
    query = db.query(StockTransaction).join(Product).join(User).outerjoin(Supplier)
    
    # 날짜 필터 (서울 시간대 사용)
    if date_from:
        try:
            from_date = parse_date_with_timezone(date_from)
            query = query.filter(StockTransaction.created_at >= from_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    if date_to:
        try:
            to_date = parse_date_with_timezone(date_to)
            to_date = to_date.replace(hour=23, minute=59, second=59)
            query = query.filter(StockTransaction.created_at <= to_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # 거래처 필터
    if supplier_id:
        query = query.filter(StockTransaction.supplier_id == supplier_id)
    
    # 거래 유형 필터
    if transaction_type:
        query = query.filter(StockTransaction.transaction_type == transaction_type)
    
    # 제품 ID 필터
    if product_id:
        query = query.filter(StockTransaction.product_id == product_id)
    
    # 제품명 검색 필터
    if product_search:
        query = query.filter(Product.name.contains(product_search))
    
    # 카테고리 필터
    if category and category != "all":
        if category == "uncategorized":
            query = query.filter(Product.category.is_(None))
        else:
            query = query.filter(Product.category == category)
    
    # 라트 번호 검색 필터
    if lot_number:
        query = query.filter(StockTransaction.lot_number.contains(lot_number))
    
    # 모든 거래 내역 조회
    transactions = query.order_by(StockTransaction.created_at.desc()).all()
    
    # CSV 생성
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 헤더 작성
    writer.writerow([
        '거래일시', '제품명', '거래유형', '수량', 'LOT번호', 
        '거래처', '담당자', '비고'
    ])
    
    # 데이터 작성
    for transaction in transactions:
        # 시간대를 고려한 날짜 포맷팅
        formatted_time = format_datetime_for_display(transaction.created_at)
        writer.writerow([
            formatted_time,
            transaction.product.name,
            '입고' if transaction.transaction_type == 'in' else '출고',
            transaction.quantity,
            transaction.lot_number or '',
            transaction.supplier.name if transaction.supplier else '',
            transaction.user.full_name,
            transaction.notes or ''
        ])
    
    # 파일명 생성 (서울 시간대 사용)
    current_time = get_seoul_time()
    filename = f"거래내역_{current_time.strftime('%Y%m%d_%H%M%S')}.csv"
    
    # CSV 데이터를 바이트로 변환
    output.seek(0)
    csv_data = output.getvalue()
    output.close()
    
    # 한글 파일명을 위한 인코딩
    encoded_filename = filename.encode('utf-8').decode('latin-1')
    
    return StreamingResponse(
        io.BytesIO(csv_data.encode('utf-8-sig')),  # BOM 추가로 한글 지원
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{encoded_filename}"'}
    )

# 토큰 갱신 API
@app.post("/api/refresh-token")
async def refresh_token(refresh_token: str = Cookie(None)):
    """리프레시 토큰을 사용하여 새로운 액세스 토큰을 발급합니다."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 필요합니다")
    
    from auth import verify_refresh_token, create_access_token
    
    username = verify_refresh_token(refresh_token)
    if not username:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다")
    
    # 새로운 액세스 토큰 생성
    new_access_token = create_access_token(data={"sub": username})
    
    response = {"access_token": new_access_token, "token_type": "bearer"}
    
    # 새로운 액세스 토큰을 쿠키에 설정
    response_obj = {"detail": "토큰이 갱신되었습니다"}
    response_obj = RedirectResponse(url="/dashboard", status_code=302)
    response_obj.set_cookie(
        key="access_token", 
        value=new_access_token, 
        httponly=False,
        max_age=604800,  # 7일
        secure=False,
        samesite="lax"
    )
    
    return response_obj

# 토큰 상태 확인 API
@app.get("/api/token-status")
async def get_token_status(access_token: str = Cookie(None), refresh_token: str = Cookie(None)):
    """토큰의 상태를 확인합니다."""
    from auth import is_token_expired, get_token_expiry_time
    
    if not access_token and not refresh_token:
        return {"status": "no_token", "message": "토큰이 없습니다"}
    
    result = {}
    
    if access_token:
        is_expired = is_token_expired(access_token)
        expiry_time = get_token_expiry_time(access_token)
        result["access_token"] = {
            "exists": True,
            "expired": is_expired,
            "expiry_time": expiry_time.isoformat() if expiry_time else None
        }
    else:
        result["access_token"] = {"exists": False}
    
    if refresh_token:
        is_expired = is_token_expired(refresh_token)
        expiry_time = get_token_expiry_time(refresh_token)
        result["refresh_token"] = {
            "exists": True,
            "expired": is_expired,
            "expiry_time": expiry_time.isoformat() if expiry_time else None
        }
    else:
        result["refresh_token"] = {"exists": False}
    
    return result

# 연결 풀 상태 확인 엔드포인트 (디버그용)
@app.get("/api/debug/pool-status")
async def get_pool_status():
    """데이터베이스 연결 풀 상태를 반환합니다."""
    from database import get_pool_status
    return get_pool_status()

# 연결 풀 리셋 엔드포인트 (디버그용)
@app.post("/api/debug/reset-pool")
async def reset_pool():
    """데이터베이스 연결 풀을 리셋합니다."""
    from database import reset_pool
    reset_pool()
    return {"message": "연결 풀이 리셋되었습니다."}

# ==================== 새로운 주문 관리 시스템 API ====================

# 주문 생성
@app.post("/api/orders")
async def create_order(
    order: OrderCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """새로운 주문을 생성합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 거래처 존재 확인
    supplier = db.query(Supplier).filter(Supplier.id == order.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="거래처를 찾을 수 없습니다")
    
    # 주문번호 생성 (YYYYMMDD-XXXX 형식)
    today = datetime.utcnow().strftime("%Y%m%d")
    last_order = db.query(Order).filter(Order.order_number.like(f"{today}-%")).order_by(Order.id.desc()).first()
    if last_order:
        last_number = int(last_order.order_number.split('-')[1])
        order_number = f"{today}-{last_number + 1:04d}"
    else:
        order_number = f"{today}-0001"
    
    # 날짜 형식 변환
    delivery_date = None
    if order.delivery_date:
        if isinstance(order.delivery_date, str):
            try:
                delivery_date = datetime.fromisoformat(order.delivery_date.replace('Z', '+00:00'))
            except ValueError:
                # ISO 형식이 아닌 경우 다른 형식 시도
                try:
                    delivery_date = datetime.strptime(order.delivery_date, '%Y-%m-%d')
                except ValueError:
                    raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다")
        else:
            delivery_date = order.delivery_date
    
    # 주문 생성
    db_order = Order(
        order_number=order_number,
        supplier_id=order.supplier_id,
        user_id=user.id,
        delivery_date=delivery_date,
        total_amount=order.total_amount,
        currency=order.currency,
        priority=order.priority,
        payment_type=order.payment_type,
        notes=order.notes,
        status="pending"
    )
    
    db.add(db_order)
    db.flush()  # ID를 얻기 위해 flush
    
    # 주문 아이템 생성
    for item in order.items:
        # 제품 존재 확인
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"제품 ID {item.product_id}를 찾을 수 없습니다")
        
        total_price = item.quantity * item.unit_price
        db_item = OrderItem(
            order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=total_price,
            remaining_quantity=item.quantity,
            notes=item.notes
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_order)
    
    return {"message": "주문이 생성되었습니다", "order_id": db_order.id, "order_number": order_number}

# 주문 목록 조회
@app.get("/api/orders")
async def get_orders(
    supplier_id: Optional[int] = None,
    status: Optional[str] = None,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문 목록을 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        # 임시로 인증 없이 테스트
        pass
    
    try:
        # 테이블 존재 여부 확인
        db.execute(text("SELECT 1 FROM orders LIMIT 1"))
        db.execute(text("SELECT 1 FROM suppliers LIMIT 1"))
        
        query = db.query(Order).join(Supplier)
        
        if supplier_id:
            query = query.filter(Order.supplier_id == supplier_id)
        if status:
            query = query.filter(Order.status == status)
        
        orders = query.order_by(Order.created_at.desc()).all()
        
        return {
            "orders": [
                {
                    "id": o.id,
                    "order_number": o.order_number,
                    "supplier_id": o.supplier_id,
                    "supplier_name": o.supplier.name,
                    "total_amount": o.total_amount,
                    "currency": o.currency,
                    "status": o.status,
                    "priority": o.priority,
                    "payment_type": o.payment_type,
                    "order_date": o.order_date.isoformat(),
                    "delivery_date": o.delivery_date.isoformat() if o.delivery_date else None,
                    "notes": o.notes,
                    "created_at": o.created_at.isoformat()
                }
                for o in orders
            ]
        }
    except Exception as e:
        print(f"DEBUG: orders 테이블 조회 중 오류: {e}")
        # 테이블이 없으면 생성 시도
        try:
            Base.metadata.create_all(bind=engine)
            print("orders 테이블을 생성했습니다.")
            return {"orders": []}
        except Exception as create_error:
            print(f"DEBUG: 테이블 생성 중 오류: {create_error}")
            raise HTTPException(status_code=500, detail=f"데이터베이스 오류: {str(e)}")

# 주문 상세 조회
@app.get("/api/orders/{order_id}")
async def get_order_detail(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문 상세 정보를 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
    
    # 주문 아이템 조회
    order_items = db.query(OrderItem).join(Product).filter(OrderItem.order_id == order_id).all()
    
    return {
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "supplier_name": order.supplier.name,
            "total_amount": order.total_amount,
            "currency": order.currency,
            "status": order.status,
            "priority": order.priority,
            "order_date": order.order_date.isoformat(),
            "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
            "notes": order.notes,
            "created_at": order.created_at.isoformat()
        },
        "items": [
            {
                "id": item.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "supplied_quantity": item.supplied_quantity,
                "remaining_quantity": item.remaining_quantity,
                "notes": item.notes
            }
            for item in order_items
        ]
    }

# 선납금 추가
@app.post("/api/orders/{order_id}/advance-payment")
async def add_advance_payment(
    order_id: int,
    payment: AdvancePaymentCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문에 대한 선납금을 추가합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 주문 존재 확인
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
    
    # 선납금 생성
    db_payment = AdvancePayment(
        order_id=order_id,
        user_id=user.id,
        amount=payment.amount,
        currency=payment.currency,
        payment_method=payment.payment_method,
        payment_date=payment.payment_date,
        reference_number=payment.reference_number,
        notes=payment.notes,
        status="completed" if payment.payment_date else "pending"
    )
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    
    # 선납금 잔액 업데이트
    update_prepayment_balance(db, order.supplier_id, payment.amount, "add")
    
    return {"message": "선납금이 추가되었습니다", "payment_id": db_payment.id}

# 선납금 목록 조회
@app.get("/api/orders/{order_id}/advance-payments")
async def get_advance_payments(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문의 선납금 목록을 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    payments = db.query(AdvancePayment).filter(AdvancePayment.order_id == order_id).all()
    
    return {
        "payments": [
            {
                "id": p.id,
                "amount": p.amount,
                "currency": p.currency,
                "payment_method": p.payment_method,
                "status": p.status,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "reference_number": p.reference_number,
                "notes": p.notes,
                "created_at": p.created_at.isoformat()
            }
            for p in payments
        ]
    }

# 공급 일정 생성 (품목별 계획 수량 지원)
@app.post("/api/orders/{order_id}/supply-schedule")
async def create_supply_schedule(
    order_id: int,
    schedule_data: dict,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문에 대한 공급 일정을 생성합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 주문 존재 확인
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
    
    schedule_date = schedule_data.get("schedule_date")
    notes = schedule_data.get("notes")
    items = schedule_data.get("items", [])
    
    if not schedule_date:
        raise HTTPException(status_code=400, detail="공급 예정일이 필요합니다")
    
    if not items:
        raise HTTPException(status_code=400, detail="최소 하나의 품목이 필요합니다")
    
    # 날짜 형식 변환
    if isinstance(schedule_date, str):
        try:
            schedule_date = datetime.fromisoformat(schedule_date.replace('Z', '+00:00'))
        except ValueError:
            try:
                schedule_date = datetime.strptime(schedule_date, '%Y-%m-%d')
            except ValueError:
                raise HTTPException(status_code=400, detail="잘못된 날짜 형식입니다")
    
    # 총 계획 수량 계산
    total_planned_quantity = sum(item.get("planned_quantity", 0) for item in items)
    
    # 공급 일정 생성
    db_schedule = SupplySchedule(
        order_id=order_id,
        user_id=user.id,
        schedule_date=schedule_date,
        planned_quantity=total_planned_quantity,
        notes=notes,
        status="scheduled"
    )
    
    db.add(db_schedule)
    db.flush()  # ID를 얻기 위해 flush
    
    # 각 품목별로 주문 아이템 업데이트 (공급된 수량 증가)
    for item in items:
        order_item_id = item.get("order_item_id")
        planned_quantity = item.get("planned_quantity", 0)
        
        if planned_quantity > 0:
            # 주문 아이템 조회 및 업데이트
            order_item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
            if order_item:
                # 공급된 수량 증가
                order_item.supplied_quantity += planned_quantity
                order_item.remaining_quantity -= planned_quantity
                
                # 남은 수량이 0 이하가 되지 않도록 체크
                if order_item.remaining_quantity < 0:
                    order_item.remaining_quantity = 0
    
    db.commit()
    db.refresh(db_schedule)
    
    return {"message": "공급 일정이 생성되었습니다", "schedule_id": db_schedule.id}

# 공급 일정 목록 조회
@app.get("/api/orders/{order_id}/supply-schedules")
async def get_supply_schedules(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문의 공급 일정 목록을 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    schedules = db.query(SupplySchedule).filter(SupplySchedule.order_id == order_id).all()
    
    return {
        "schedules": [
            {
                "id": s.id,
                "schedule_date": s.schedule_date.isoformat(),
                "planned_quantity": s.planned_quantity,
                "actual_quantity": s.actual_quantity,
                "status": s.status,
                "notes": s.notes,
                "created_at": s.created_at.isoformat()
            }
            for s in schedules
        ]
    }

# 공급 일정 업데이트
@app.put("/api/supply-schedules/{schedule_id}")
async def update_supply_schedule(
    schedule_id: int,
    schedule_update: SupplyScheduleUpdate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """공급 일정을 업데이트합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    schedule = db.query(SupplySchedule).filter(SupplySchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="공급 일정을 찾을 수 없습니다")
    
    # 업데이트
    if schedule_update.actual_quantity is not None:
        schedule.actual_quantity = schedule_update.actual_quantity
    if schedule_update.status:
        schedule.status = schedule_update.status
    if schedule_update.notes:
        schedule.notes = schedule_update.notes
    
    db.commit()
    
    return {"message": "공급 일정이 업데이트되었습니다"}

# 문서 작업 생성
@app.post("/api/orders/{order_id}/document-work")
async def create_document_work(
    order_id: int,
    document: DocumentWorkCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문에 대한 문서 작업을 생성합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    # 주문 존재 확인
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
    
    # 문서 작업 생성
    db_document = DocumentWork(
        order_id=order_id,
        user_id=user.id,
        document_type=document.document_type,
        due_date=document.due_date,
        notes=document.notes,
        status="pending"
    )
    
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    
    return {"message": "문서 작업이 생성되었습니다", "document_id": db_document.id}

# 문서 작업 목록 조회
@app.get("/api/orders/{order_id}/document-works")
async def get_document_works(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문의 문서 작업 목록을 조회합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    documents = db.query(DocumentWork).filter(DocumentWork.order_id == order_id).all()
    
    return {
        "documents": [
            {
                "id": d.id,
                "document_type": d.document_type,
                "status": d.status,
                "start_date": d.start_date.isoformat() if d.start_date else None,
                "completion_date": d.completion_date.isoformat() if d.completion_date else None,
                "due_date": d.due_date.isoformat() if d.due_date else None,
                "notes": d.notes,
                "file_path": d.file_path,
                "created_at": d.created_at.isoformat()
            }
            for d in documents
        ]
    }

# 주문 상태 업데이트
@app.put("/api/orders/{order_id}/status")
async def update_order_status(
    order_id: int,
    status_update: OrderUpdate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문 상태를 업데이트합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
    
    # 완료된 주문은 상태 변경 불가
    if order.status == "completed":
        raise HTTPException(status_code=400, detail="완료된 주문은 상태를 변경할 수 없습니다")
    
    # 상태 업데이트
    if status_update.status:
        order.status = status_update.status
    if status_update.delivery_date:
        order.delivery_date = status_update.delivery_date
    if status_update.priority:
        order.priority = status_update.priority
    if status_update.notes:
        order.notes = status_update.notes
    
    db.commit()
    
    return {"message": "주문 상태가 업데이트되었습니다"}

# 주문 삭제
@app.delete("/api/orders/{order_id}")
async def delete_order(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """주문을 삭제합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다")
    
    # 취소된 주문만 삭제 가능
    if order.status != "cancelled":
        raise HTTPException(status_code=400, detail="취소된 주문만 삭제할 수 있습니다")
    
    # 관련 데이터 삭제 (CASCADE 설정으로 자동 삭제되지만 명시적으로 처리)
    # 주문 아이템 삭제
    db.query(OrderItem).filter(OrderItem.order_id == order_id).delete()
    
    # 공급 일정 삭제
    db.query(SupplySchedule).filter(SupplySchedule.order_id == order_id).delete()
    
    # 선납금 삭제
    db.query(AdvancePayment).filter(AdvancePayment.order_id == order_id).delete()
    
    # 문서 작업 삭제
    db.query(DocumentWork).filter(DocumentWork.order_id == order_id).delete()
    
    # 주문 삭제
    db.delete(order)
    db.commit()
    
    return {"message": "주문이 삭제되었습니다"}

# 문서 작업 업데이트
@app.put("/api/document-works/{document_id}")
async def update_document_work(
    document_id: int,
    document_update: DocumentWorkUpdate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """문서 작업을 업데이트합니다."""
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    document = db.query(DocumentWork).filter(DocumentWork.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="문서 작업을 찾을 수 없습니다")
    
    # 업데이트
    if document_update.status:
        document.status = document_update.status
        if document_update.status == "in_progress" and not document.start_date:
            document.start_date = datetime.utcnow()
        elif document_update.status == "completed" and not document.completion_date:
            document.completion_date = datetime.utcnow()
    
    if document_update.start_date:
        document.start_date = document_update.start_date
    if document_update.completion_date:
        document.completion_date = document_update.completion_date
    if document_update.notes:
        document.notes = document_update.notes
    if document_update.file_path:
        document.file_path = document_update.file_path
    
    db.commit()
    
    return {"message": "문서 작업이 업데이트되었습니다"}




# 재고 거래 시 선납금 자동 차감
def auto_deduct_prepayment(db: Session, supplier_id: int, amount: float, stock_transaction_id: int, user_id: int):
    """재고 거래 시 선납금을 자동으로 차감합니다."""
    # 선납금 잔액 확인
    balance = db.query(PrepaymentBalance).filter(
        PrepaymentBalance.supplier_id == supplier_id
    ).first()
    
    if not balance or balance.balance <= 0:
        return False  # 선납금 없음
    
    # 사용할 금액 결정 (잔액과 요청 금액 중 작은 값)
    deduct_amount = min(balance.balance, amount)
    
    if deduct_amount > 0:
        # 선납금 사용 거래 생성
        payment = PaymentTransaction(
            supplier_id=supplier_id,
            user_id=user_id,
            stock_transaction_id=stock_transaction_id,
            payment_type="settlement",
            amount=-deduct_amount,
            payment_method="prepayment",
            payment_date=datetime.utcnow(),
            notes=f"재고 거래 #{stock_transaction_id} 자동 차감",
            status="completed"
        )
        
        db.add(payment)
        
        # 잔액 업데이트
        update_prepayment_balance(db, supplier_id, deduct_amount, "subtract")
        
        return True
    
    return False

def update_prepayment_balance(db: Session, supplier_id: int, amount: float, operation: str):
    """선납금 잔액을 업데이트합니다."""
    balance = db.query(PrepaymentBalance).filter(
        PrepaymentBalance.supplier_id == supplier_id
    ).first()
    
    if not balance:
        # 새로 생성
        balance = PrepaymentBalance(
            supplier_id=supplier_id,
            balance=amount if operation == "add" else 0,
            total_prepaid=amount if operation == "add" else 0,
            total_used=0 if operation == "add" else amount
        )
        db.add(balance)
    else:
        # 기존 잔액 업데이트
        if operation == "add":
            balance.balance += amount
            balance.total_prepaid += amount
        else:  # subtract
            balance.balance -= amount
            balance.total_used += amount
        
        balance.last_updated = datetime.utcnow()
    
    db.commit()

def migrate_create_payment_tables():
    """결제 관련 테이블들을 생성합니다."""
    try:
        from database import SessionLocal
        db = SessionLocal()
        
        print("결제 관련 테이블들을 생성하는 중...")
        
        # PaymentTransaction 테이블 생성
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS payment_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                stock_transaction_id INTEGER,
                payment_type VARCHAR(20) NOT NULL,
                amount REAL NOT NULL,
                currency VARCHAR(3) DEFAULT 'KRW',
                status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(50),
                payment_date DATETIME,
                due_date DATETIME,
                reference_number VARCHAR(100),
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (stock_transaction_id) REFERENCES stock_transactions (id)
            )
        """))
        
        # PaymentSchedule 테이블 생성
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS payment_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                stock_transaction_id INTEGER,
                total_amount REAL NOT NULL,
                paid_amount REAL DEFAULT 0,
                remaining_amount REAL NOT NULL,
                due_date DATETIME NOT NULL,
                payment_terms VARCHAR(50),
                status VARCHAR(20) DEFAULT 'pending',
                is_active BOOLEAN DEFAULT 1,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (stock_transaction_id) REFERENCES stock_transactions (id)
            )
        """))
        
        # PrepaymentBalance 테이블 생성
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS prepayment_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                supplier_id INTEGER NOT NULL UNIQUE,
                balance REAL DEFAULT 0,
                total_prepaid REAL DEFAULT 0,
                total_used REAL DEFAULT 0,
                currency VARCHAR(3) DEFAULT 'KRW',
                is_active BOOLEAN DEFAULT 1,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
            )
        """))
        
        # 인덱스 생성
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_transactions_supplier ON payment_transactions (supplier_id)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_transactions_date ON payment_transactions (payment_date)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_schedules_due_date ON payment_schedules (due_date)"))
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_payment_schedules_status ON payment_schedules (status)"))
        
        db.commit()
        db.close()
        
        print("결제 관련 테이블 생성 완료!")
        return True
    except Exception as e:
        print(f"결제 테이블 생성 실패: {e}")
        return False

# 주문관리 페이지
@app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, access_token: str = Cookie(None)):
    """주문관리 페이지"""
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("orders.html", {
        "request": request,
        "user": user
    })

if __name__ == "__main__":
    # 데이터베이스 마이그레이션 실행
    print("데이터베이스 마이그레이션을 확인하는 중...")
    
    # 모든 테이블 존재 여부 확인 및 생성
    ensure_all_tables_exist()
    
    # 주문 관련 테이블이 없으면 생성
    if not check_order_tables_exist():
        print("주문 관련 테이블이 없습니다. 생성합니다.")
        Base.metadata.create_all(bind=engine)
        print("주문 관련 테이블 생성 완료!")
    else:
        print("주문 관련 테이블이 이미 존재합니다.")
    
    # 결제 관련 테이블이 없으면 생성
    if not check_payment_tables_exist():
        print("결제 관련 테이블이 없습니다. 생성합니다.")
        migrate_create_payment_tables()
    else:
        print("결제 관련 테이블이 이미 존재합니다.")
    
    # 거래처 정렬 순서 컬럼이 없으면 추가
    if not check_supplier_sort_order_column_exists():
        print("거래처 정렬 순서 컬럼이 없습니다. 추가합니다.")
        migrate_add_supplier_sort_order()
    else:
        print("거래처 정렬 순서 컬럼이 이미 존재합니다.")
    
    uvicorn.run(app, host="0.0.0.0", port=8100)
