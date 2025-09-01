#!/bin/bash

echo "🏢 ERP 시스템 NAS 실행 스크립트"
echo "=================================="

# 현재 디렉토리 확인
echo "현재 디렉토리: $(pwd)"

# Docker 이미지 로드
echo "1. Docker 이미지 로드 중..."
if [ -f "erp-system_latest.tar" ]; then
    sudo docker load < erp-system_latest.tar
    if [ $? -eq 0 ]; then
        echo "✅ 이미지 로드 완료"
    else
        echo "❌ 이미지 로드 실패"
        exit 1
    fi
else
    echo "❌ erp-system_latest.tar 파일을 찾을 수 없습니다."
    exit 1
fi

# 기존 컨테이너 정리
echo "2. 기존 컨테이너 정리..."
sudo docker stop erp-system >/dev/null 2>&1
sudo docker rm erp-system >/dev/null 2>&1
echo "✅ 기존 컨테이너 정리 완료"

# 필요한 디렉토리 생성
echo "3. 필요한 디렉토리 생성..."
mkdir -p /volume1/docker/erp/data
mkdir -p /volume1/docker/erp/logs
mkdir -p /volume1/docker/erp/backups
echo "✅ 디렉토리 생성 완료"

# 컨테이너 실행
echo "4. 컨테이너 실행 중..."
sudo docker run -d \
    --name erp-system \
    -p 8100:8100 \
    -v "/volume1/docker/erp/data:/app/data" \
    -v "/volume1/docker/erp/logs:/app/logs" \
    -v "/volume1/docker/erp/backups:/app/backups" \
    -e PYTHONPATH=/app \
    -e PYTHONUNBUFFERED=1 \
    -e DB_DIR=/app/data \
    -e TZ=Asia/Seoul \
    --restart unless-stopped \
    erp-system:latest

if [ $? -eq 0 ]; then
    echo "✅ 컨테이너 실행 성공!"
else
    echo "❌ 컨테이너 실행 실패"
    exit 1
fi

# 컨테이너 상태 확인
echo "5. 컨테이너 상태 확인..."
sleep 3
sudo docker ps | grep erp-system

# 헬스체크
echo "6. 애플리케이션 헬스체크..."
sleep 10
if curl -f -s http://localhost:8100/login > /dev/null; then
    echo "✅ 애플리케이션이 정상적으로 응답합니다."
else
    echo "⚠️  애플리케이션 헬스체크에 실패했습니다. 잠시 후 다시 확인해주세요."
fi

echo ""
echo "=================================="
echo "🎉 ERP 시스템이 성공적으로 실행되었습니다!"
echo ""
echo "📱 접속 정보:"
echo "   - 웹 인터페이스: http://[NAS_IP]:8100"
echo "   - 예시: http://192.168.68.50:8100"
echo ""
echo "👤 기본 관리자 계정:"
echo "   - 사용자명: admin"
echo "   - 비밀번호: admin123"
echo "   - 이메일: admin@erp.com"
echo ""
echo "📁 데이터 저장 위치:"
echo "   - 데이터베이스: /volume1/docker/erp/data/erp_system.db"
echo "   - 로그 파일: /volume1/docker/erp/logs/"
echo "   - 백업 파일: /volume1/docker/erp/backups/"
echo ""
echo "📋 유용한 명령어:"
echo "   - 로그 확인: sudo docker logs erp-system"
echo "   - 컨테이너 중지: sudo docker stop erp-system"
echo "   - 컨테이너 재시작: sudo docker restart erp-system"
echo "   - 컨테이너 삭제: sudo docker rm -f erp-system"
echo "   - 컨테이너 상태: sudo docker ps -f name=erp-system"
echo ""
echo "🔄 자동 재시작이 설정되었습니다 (unless-stopped)"
echo "   시스템 재부팅 시 컨테이너가 자동으로 시작됩니다."
echo ""
