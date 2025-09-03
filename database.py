from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# SQLite 데이터베이스 설정
# Windows 환경에서는 ./data 디렉토리에 저장
DB_DIR = os.getenv("DB_DIR", "./data")
os.makedirs(DB_DIR, exist_ok=True)
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_DIR}/erp_system.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},  # SQLite 전용 설정
    # 연결 풀 설정 추가
    pool_size=20,           # 기본 연결 풀 크기 증가 (기본값: 5)
    max_overflow=30,        # 오버플로우 연결 수 증가 (기본값: 10)
    pool_timeout=60,        # 연결 대기 시간 증가 (기본값: 30초)
    pool_recycle=3600,      # 연결 재사용 시간 (1시간)
    pool_pre_ping=True      # 연결 유효성 검사
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_pool_status():
    """연결 풀 상태를 반환합니다."""
    pool = engine.pool
    return {
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalid()
    }

def reset_pool():
    """연결 풀을 리셋합니다."""
    engine.dispose()
    print("데이터베이스 연결 풀이 리셋되었습니다.")
