@echo off
echo === 도커 컨테이너 내 시간대 테스트 ===
echo.

echo 1. 컨테이너 실행 상태 확인...
docker-compose ps

echo.
echo 2. 컨테이너 내 시간대 테스트 실행...
docker-compose exec erp-system python timezone_test.py

echo.
echo 3. 컨테이너 내 현재 시간 확인...
docker-compose exec erp-system date

echo.
echo 4. 컨테이너 내 환경 변수 확인...
docker-compose exec erp-system env | findstr TZ

echo.
echo 5. 컨테이너 내 시간대 파일 확인...
docker-compose exec erp-system ls -la /etc/timezone
docker-compose exec erp-system cat /etc/timezone

echo.
echo === 테스트 완료 ===
pause

