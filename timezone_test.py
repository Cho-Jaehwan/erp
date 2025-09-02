#!/usr/bin/env python3
"""
시간대 테스트 스크립트
도커 환경에서 시간대가 올바르게 설정되었는지 확인합니다.
"""

import os
import time
from datetime import datetime
import pytz

def test_timezone():
    print("=== 시간대 테스트 ===")
    print()
    
    # 환경 변수 확인
    print("1. 환경 변수:")
    print(f"   TZ: {os.environ.get('TZ', 'Not set')}")
    print()
    
    # 시스템 시간대 정보
    print("2. 시스템 시간대 정보:")
    print(f"   time.timezone: {time.timezone}")
    print(f"   time.tzname: {time.tzname}")
    print()
    
    # 다양한 시간 표시
    print("3. 시간 비교:")
    utc_now = datetime.utcnow()
    local_now = datetime.now()
    seoul_tz = pytz.timezone('Asia/Seoul')
    seoul_now = datetime.now(seoul_tz)
    
    print(f"   UTC 시간:     {utc_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   로컬 시간:    {local_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   서울 시간:    {seoul_now.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 시간대 오프셋 확인
    print("4. 시간대 오프셋:")
    utc_offset = seoul_now.utcoffset()
    print(f"   서울 시간대 오프셋: {utc_offset}")
    print()
    
    # 시간대 이름 확인
    print("5. 시간대 이름:")
    print(f"   서울 시간대 이름: {seoul_now.tzname()}")
    print()
    
    # DST (일광절약시간) 확인
    print("6. DST 정보:")
    print(f"   DST 적용 여부: {seoul_now.dst()}")
    print()
    
    print("=== 테스트 완료 ===")

if __name__ == "__main__":
    test_timezone()

