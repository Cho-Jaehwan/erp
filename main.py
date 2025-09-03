from fastapi import FastAPI, Request, Depends, HTTPException, status, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, text
import uvicorn
from datetime import datetime, timedelta
from typing import List, Optional
import os
import io
import csv
import pytz

from database import get_db, engine
from models import User, Product, StockTransaction, Supplier, AuditLog, Base
from auth import get_current_user, get_current_admin, create_access_token, create_refresh_token, verify_password, get_password_hash
from schemas import UserCreate, UserLogin, ProductCreate, ProductUpdate, StockTransactionCreate, SupplierCreate, SupplierUpdate, BulkStockOutCreate
import subprocess
import sys

def check_database_exists():
    """데이터베이스 파일 존재 여부 확인"""
    from database import DB_DIR
    db_path = os.path.join(DB_DIR, "erp_system.db")
    return os.path.exists(db_path)

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
    print(f"DEBUG: 현재 서울 시간: {seoul_time}")
    return seoul_time

def parse_date_with_timezone(date_string: str) -> datetime:
    """날짜 문자열을 서울 시간대로 파싱합니다."""
    try:
        # 날짜만 있는 경우 (YYYY-MM-DD)
        if len(date_string) == 10:
            naive_date = datetime.strptime(date_string, "%Y-%m-%d")
            localized_date = SEOUL_TZ.localize(naive_date)
            print(f"DEBUG: 날짜 파싱 - 입력: {date_string}, 결과: {localized_date}")
            return localized_date
        # 날짜와 시간이 있는 경우
        else:
            naive_date = datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
            localized_date = SEOUL_TZ.localize(naive_date)
            print(f"DEBUG: 날짜시간 파싱 - 입력: {date_string}, 결과: {localized_date}")
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
    print(f"DEBUG: 쿠키에서 받은 액세스 토큰: {access_token}")
    print(f"DEBUG: 쿠키에서 받은 리프레시 토큰: {refresh_token}")
    
    if not access_token and not refresh_token:
        print("DEBUG: 토큰이 없습니다")
        return None
    
    from auth import verify_token, verify_refresh_token, is_token_expired, create_access_token
    from database import SessionLocal
    
    # 액세스 토큰이 있고 유효한 경우
    if access_token and not is_token_expired(access_token):
        username = verify_token(access_token)
        if username:
            print(f"DEBUG: 액세스 토큰에서 추출한 사용자명: {username}")
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_approved:
                    print("DEBUG: 액세스 토큰으로 사용자 인증 성공")
                    return user
            except Exception as e:
                print(f"DEBUG: 데이터베이스 조회 중 오류: {e}")
            finally:
                db.close()
    
    # 액세스 토큰이 만료되었거나 없고, 리프레시 토큰이 있는 경우
    if refresh_token:
        username = verify_refresh_token(refresh_token)
        if username:
            print(f"DEBUG: 리프레시 토큰에서 추출한 사용자명: {username}")
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.username == username).first()
                if user and user.is_approved:
                    print("DEBUG: 리프레시 토큰으로 사용자 인증 성공")
                    return user
            except Exception as e:
                print(f"DEBUG: 데이터베이스 조회 중 오류: {e}")
            finally:
                db.close()
    
    print("DEBUG: 토큰 검증 실패")
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
    print(f"DEBUG: 총 제품 수: {len(all_products)}")
    for product in all_products:
        category = product.category or '미분류'
        print(f"DEBUG: 제품 - 이름: {product.name}, 카테고리: {category}, 재고: {product.stock_quantity}")
        if category not in category_products:
            category_products[category] = []
        category_products[category].append(product)
    
    print(f"DEBUG: 카테고리별 제품 그룹: {category_products}")
    
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
    return templates.TemplateResponse("inventory.html", {
        "request": request,
        "products": products
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
    db.commit()
    db.refresh(db_product)
    return {"message": "제품이 추가되었습니다", "product": db_product}

# 제품 목록 조회 API
@app.get("/api/products")
async def get_products(access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    products = db.query(Product).all()
    return products

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
    
    # 필드 업데이트
    update_data = product_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_product, field, value)
    
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
    products = db.query(Product).all()
    return templates.TemplateResponse("stock_in.html", {
        "request": request,
        "products": products
    })

# 출고 페이지
@app.get("/stock/out", response_class=HTMLResponse)
async def stock_out_page(request: Request, access_token: str = Cookie(None)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    
    db = next(get_db())
    products = db.query(Product).all()
    return templates.TemplateResponse("stock_out.html", {
        "request": request,
        "products": products
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
    stock_transaction = StockTransaction(
        product_id=transaction.product_id,
        user_id=user.id,
        supplier_id=transaction.supplier_id,
        transaction_type="in",
        quantity=transaction.quantity,
        lot_number=transaction.lot_number,
        location=transaction.location,
        notes=transaction.notes,
        created_at=current_time
    )
    db.add(stock_transaction)
    db.commit()
    
    return {"message": "입고가 완료되었습니다"}

# 출고 처리
@app.post("/stock/out")
async def process_stock_out(transaction: StockTransactionCreate, access_token: str = Cookie(None), db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    product = db.query(Product).filter(Product.id == transaction.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="제품을 찾을 수 없습니다")
    
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
        
        if lot_current_stock < transaction.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"LOT {transaction.lot_number}의 재고가 부족합니다. (LOT 재고: {lot_current_stock}개, 요청 수량: {transaction.quantity}개)"
            )
    
    # 재고 수량 감소
    product.stock_quantity -= transaction.quantity
    
    # 출고 거래 기록 (서울 시간대 사용)
    current_time = get_seoul_time()
    stock_transaction = StockTransaction(
        product_id=transaction.product_id,
        user_id=user.id,
        supplier_id=transaction.supplier_id,
        transaction_type="out",
        quantity=transaction.quantity,
        lot_number=transaction.lot_number,
        location=transaction.location,
        notes=transaction.notes,
        created_at=current_time
    )
    db.add(stock_transaction)
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
    
    # 모든 제품의 재고 확인
    product_ids = [item.product_id for item in bulk_data.items]
    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    
    if len(products) != len(product_ids):
        raise HTTPException(status_code=404, detail="일부 제품을 찾을 수 없습니다")
    
    # 재고 부족 확인 및 LOT별 재고 확인
    for item in bulk_data.items:
        product = next(p for p in products if p.id == item.product_id)
        
        # 전체 재고 확인
        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400, 
                detail=f"제품 '{product.name}'의 재고가 부족합니다. (현재 재고: {product.stock_quantity}개, 요청 수량: {item.quantity}개)"
            )
        
        # LOT별 재고 확인 (LOT 번호가 있는 경우)
        if item.lot_number:
            # 해당 LOT의 입고 수량 계산
            in_quantity = db.query(func.sum(StockTransaction.quantity)).filter(
                StockTransaction.product_id == item.product_id,
                StockTransaction.lot_number == item.lot_number,
                StockTransaction.transaction_type == "in"
            ).scalar() or 0
            
            # 해당 LOT의 출고 수량 계산
            out_quantity = db.query(func.sum(StockTransaction.quantity)).filter(
                StockTransaction.product_id == item.product_id,
                StockTransaction.lot_number == item.lot_number,
                StockTransaction.transaction_type == "out"
            ).scalar() or 0
            
            # LOT별 현재 재고
            lot_current_stock = in_quantity - out_quantity
            
            if lot_current_stock < item.quantity:
                raise HTTPException(
                    status_code=400, 
                    detail=f"제품 '{product.name}' LOT {item.lot_number}의 재고가 부족합니다. (LOT 재고: {lot_current_stock}개, 요청 수량: {item.quantity}개)"
                )
    
    # 모든 검증이 통과하면 출고 처리
    transactions = []
    for item in bulk_data.items:
        product = next(p for p in products if p.id == item.product_id)
        
        # 재고 수량 감소
        product.stock_quantity -= item.quantity
        
        # 출고 거래 기록 (서울 시간대 사용)
        current_time = get_seoul_time()
        stock_transaction = StockTransaction(
            product_id=item.product_id,
            user_id=user.id,
            supplier_id=bulk_data.supplier_id,
            transaction_type="out",
            quantity=item.quantity,
            lot_number=item.lot_number,
            location=None,
            notes=bulk_data.notes,
            created_at=current_time
        )
        transactions.append(stock_transaction)
        db.add(stock_transaction)
    
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
    
    suppliers = db.query(Supplier).order_by(Supplier.created_at.desc()).all()
    return suppliers

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
    
    # 전체 개수 계산
    total_transactions = query.count()
    total_pages = (total_transactions + per_page - 1) // per_page
    
    # 페이지네이션 적용
    offset = (page - 1) * per_page
    transactions = query.order_by(StockTransaction.created_at.desc()).offset(offset).limit(per_page).all()
    
    print(f"DEBUG: 거래 내역 조회 결과 - 총 개수: {total_transactions}, 현재 페이지: {page}, 조회된 거래 내역: {len(transactions)}")
    for i, transaction in enumerate(transactions):
        print(f"DEBUG: 거래 내역 {i+1} - ID: {transaction.id}, 제품: {transaction.product.name if transaction.product else 'N/A'}, 유형: {transaction.transaction_type}, 수량: {transaction.quantity}, 거래처: {transaction.supplier.name if transaction.supplier else 'None'}, 작업자: {transaction.user.full_name if transaction.user else 'None'}, 작업자ID: {transaction.user_id}, 날짜: {transaction.created_at}")
    
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)
