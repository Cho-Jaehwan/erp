#!/bin/bash

echo "🏥 약품데이터 앱 NAS 실행 스크립트"
echo "=================================="

# 현재 디렉토리 확인
echo "현재 디렉토리: $(pwd)"

# Docker 이미지 로드
echo "1. Docker 이미지 로드 중..."
if [ -f "medicine-data-container.tar" ]; then
    sudo docker load < medicine-data-container.tar
    if [ $? -eq 0 ]; then
        echo "✅ 이미지 로드 완료"
    else
        echo "❌ 이미지 로드 실패"
        exit 1
    fi
else
    echo "❌ medicine-data-container.tar 파일을 찾을 수 없습니다."
    exit 1
fi

# 기존 컨테이너 정리
echo "2. 기존 컨테이너 정리..."
sudo docker stop medicine-data-app-nas >/dev/null 2>&1
sudo docker rm medicine-data-app-nas >/dev/null 2>&1
echo "✅ 기존 컨테이너 정리 완료"

# 필요한 디렉토리 생성
echo "3. 필요한 디렉토리 생성..."
mkdir -p dat_files instance config logs
echo "✅ 디렉토리 생성 완료"

# 컨테이너 실행
echo "4. 컨테이너 실행 중..."
sudo docker run -d \
    --name medicine-data-app-nas \
    -p 5000:5000 \
    -v "$(pwd)/dat_files:/app/dat_files" \
    -v "$(pwd)/instance:/app/instance" \
    -v "$(pwd)/config:/app/config" \
    -v "$(pwd)/logs:/app/logs" \
    -e FLASK_APP=app.py \
    -e FLASK_ENV=production \
    -e TZ=Asia/Seoul \
    --restart unless-stopped \
    medicine-data-app-nas

if [ $? -eq 0 ]; then
    echo "✅ 컨테이너 실행 성공!"
else
    echo "❌ 컨테이너 실행 실패"
    exit 1
fi

# 컨테이너 상태 확인
echo "5. 컨테이너 상태 확인..."
sleep 3
sudo docker ps | grep medicine-data-app-nas

echo ""
echo "=================================="
echo "🎉 약품데이터 앱이 성공적으로 실행되었습니다!"
echo ""
echo "📱 접속 정보:"
echo "   - 웹 인터페이스: http://[NAS_IP]:5000"
echo "   - 예시: http://192.168.68.50:5000"
echo ""
echo "📋 유용한 명령어:"
echo "   - 로그 확인: sudo docker logs medicine-data-app-nas"
echo "   - 컨테이너 중지: sudo docker stop medicine-data-app-nas"
echo "   - 컨테이너 재시작: sudo docker restart medicine-data-app-nas"
echo "   - 컨테이너 삭제: sudo docker rm -f medicine-data-app-nas"
echo ""

