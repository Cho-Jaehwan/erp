# Python 3.11 슬림 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 시간대 설정 (한국 시간)
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 포트 8000 노출
EXPOSE 8100

# 초기화 스크립트 생성
RUN echo '#!/bin/bash\n\
echo "=== 재고관리 시스템 시작 ==="\n\
echo "데이터베이스 초기화 중..."\n\
python init_admin.py\n\
echo "웹 서버 시작 중..."\n\
uvicorn main:app --host 0.0.0.0 --port 8100 --reload\n\
' > /app/start.sh && chmod +x /app/start.sh

# 시작 스크립트 실행
CMD ["/app/start.sh"]
