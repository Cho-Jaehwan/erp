@echo off
echo === 재고관리 시스템 도커 재빌드 및 실행 ===
echo.

echo 1. 기존 컨테이너 중지 및 제거...
docker-compose down

echo.
echo 2. 기존 이미지 제거...
docker rmi erp-웹_erp-system 2>nul

echo.
echo 3. 새로운 이미지 빌드...
docker-compose build --no-cache

echo.
echo 4. 컨테이너 실행...
docker-compose up -d

echo.
echo 5. 컨테이너 상태 확인...
docker-compose ps

echo.
echo 6. 로그 확인...
docker-compose logs -f --tail=50

echo.
echo === 완료 ===
echo 브라우저에서 http://localhost:8100 으로 접속하세요.
echo 시간대 디버깅: http://localhost:8100/api/debug/timezone
pause

