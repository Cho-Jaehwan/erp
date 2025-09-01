#!/usr/bin/env python3
"""
관리자 계정 초기화 스크립트
도커 환경에서 DB가 없으면 생성하고, 있으면 기존 DB를 사용합니다.
"""

import os
import sys
from sqlalchemy.orm import Session
from sqlalchemy import inspect
from database import SessionLocal, engine
from models import User, Base
from auth import get_password_hash

def check_database_exists():
    """데이터베이스 파일 존재 여부 확인"""
    from database import DB_DIR
    db_path = os.path.join(DB_DIR, "erp_system.db")
    return os.path.exists(db_path)

def check_tables_exist():
    """테이블 존재 여부 확인"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    required_tables = ['users', 'products', 'suppliers', 'stock_transactions']
    return all(table in existing_tables for table in required_tables)

def create_admin_user():
    """관리자 계정 생성"""
    print("=== ERP 시스템 초기화 시작 ===")
    
    # 데이터베이스 파일 존재 여부 확인
    db_exists = check_database_exists()
    print(f"데이터베이스 파일 존재: {db_exists}")
    
    # 테이블 존재 여부 확인
    tables_exist = check_tables_exist()
    print(f"필수 테이블 존재: {tables_exist}")
    
    # 데이터베이스 테이블 생성 (없는 경우에만)
    if not tables_exist:
        print("테이블을 생성합니다...")
        Base.metadata.create_all(bind=engine)
        print("테이블 생성 완료")
    else:
        print("기존 테이블을 사용합니다.")
    
    db = SessionLocal()
    try:
        # 기존 관리자 계정 확인
        existing_admin = db.query(User).filter(User.username == "flyjh0503").first()
        if existing_admin:
            print("관리자 계정이 이미 존재합니다.")
            print(f"관리자 계정 정보:")
            print(f"  - 사용자명: {existing_admin.username}")
            print(f"  - 이메일: {existing_admin.email}")
            print(f"  - 승인 상태: {'승인됨' if existing_admin.is_approved else '승인 대기'}")
            print(f"  - 관리자 권한: {'있음' if existing_admin.is_admin else '없음'}")
            return
        
        # 새 관리자 계정 생성
        admin_user = User(
            username="flyjh0503",
            email="flyjh0503@posthitech.net",
            full_name="조재환",
            hashed_password=get_password_hash("gs-4731cho"),
            is_approved=True,
            is_admin=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("관리자 계정이 성공적으로 생성되었습니다.")
        print("=========================")
        
    except Exception as e:
        print(f"❌ 관리자 계정 생성 중 오류가 발생했습니다: {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
    
    print("=== ERP 시스템 초기화 완료 ===")

def main():
    """메인 함수"""
    try:
        # 항상 관리자 계정 생성 시도 (테이블이 없으면 생성하고, 있으면 기존 것 사용)
        print("관리자 계정 초기화를 시작합니다...")
        create_admin_user()
    except Exception as e:
        print(f"❌ 초기화 중 오류가 발생했습니다: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
