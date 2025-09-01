@echo off
chcp 65001 >nul
echo ========================================
echo ERP 시스템 도커 이미지 빌드 스크립트
echo ========================================
echo.

REM 현재 디렉토리 확인
echo 현재 작업 디렉토리: %CD%
echo.

REM Docker가 실행 중인지 확인
echo Docker 상태 확인 중...
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Docker가 실행되지 않았거나 설치되지 않았습니다.
    echo Docker Desktop을 설치하고 실행한 후 다시 시도해주세요.
    pause
    exit /b 1
)
echo [성공] Docker가 정상적으로 실행 중입니다.
echo.

REM 이미지 이름과 태그 설정
set IMAGE_NAME=erp-system
set IMAGE_TAG=latest
set FULL_IMAGE_NAME=%IMAGE_NAME%:%IMAGE_TAG%

echo 이미지 정보:
echo - 이미지명: %FULL_IMAGE_NAME%
echo - 빌드 컨텍스트: %CD%
echo.

REM 기존 이미지가 있는지 확인하고 제거
echo 기존 이미지 확인 중...
docker images %IMAGE_NAME% --format "table {{.Repository}}:{{.Tag}}" | findstr %IMAGE_NAME% >nul
if %errorlevel% equ 0 (
    echo 기존 이미지를 발견했습니다. 제거 중...
    docker rmi %FULL_IMAGE_NAME% --force
    if %errorlevel% neq 0 (
        echo [경고] 기존 이미지 제거에 실패했습니다. 계속 진행합니다.
    ) else (
        echo [성공] 기존 이미지가 제거되었습니다.
    )
    echo.
)

REM .dockerignore 파일이 없으면 생성
if not exist .dockerignore (
    echo .dockerignore 파일이 없습니다. 생성 중...
    (
        echo __pycache__/
        echo *.pyc
        echo *.pyo
        echo *.pyd
        echo .Python
        echo env/
        echo venv/
        echo .env
        echo .venv
        echo .git/
        echo .gitignore
        echo README.md
        echo README_*.md
        echo *.tar.gz
        echo .DS_Store
        echo Thumbs.db
        echo *.log
        echo logs/
        echo data/
        echo .vscode/
        echo .idea/
    ) > .dockerignore
    echo [성공] .dockerignore 파일이 생성되었습니다.
    echo.
)

REM Docker 이미지 빌드
echo Docker 이미지 빌드 시작...
echo 명령어: docker build -t %FULL_IMAGE_NAME% .
echo.
docker build -t %FULL_IMAGE_NAME% .

if %errorlevel% neq 0 (
    echo [오류] Docker 이미지 빌드에 실패했습니다.
    echo 빌드 로그를 확인하고 오류를 수정한 후 다시 시도해주세요.
    pause
    exit /b 1
)

echo.
echo [성공] Docker 이미지가 성공적으로 빌드되었습니다!
echo.

REM 빌드된 이미지 정보 출력
echo 빌드된 이미지 정보:
docker images %IMAGE_NAME% --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
echo.

REM 이미지를 tar 파일로 저장
set TAR_FILENAME=%IMAGE_NAME%_%IMAGE_TAG%.tar
echo 이미지를 tar 파일로 저장 중...
echo 파일명: %TAR_FILENAME%
docker save -o %TAR_FILENAME% %FULL_IMAGE_NAME%

if %errorlevel% neq 0 (
    echo [오류] 이미지 tar 파일 저장에 실패했습니다.
    pause
    exit /b 1
)

REM 파일 크기 확인
for %%A in (%TAR_FILENAME%) do set TAR_SIZE=%%~zA
set /a TAR_SIZE_MB=%TAR_SIZE%/1024/1024

echo [성공] 이미지가 tar 파일로 저장되었습니다.
echo 파일 크기: %TAR_SIZE_MB% MB
echo 파일 위치: %CD%\%TAR_FILENAME%
echo.

REM 압축 파일 생성 (선택사항)
echo 압축 파일을 생성하시겠습니까? (y/n)
set /p COMPRESS=
if /i "%COMPRESS%"=="y" (
    echo 압축 중...
    powershell -Command "Compress-Archive -Path '%TAR_FILENAME%' -DestinationPath '%TAR_FILENAME%.zip' -Force"
    if %errorlevel% equ 0 (
        echo [성공] 압축 파일이 생성되었습니다: %TAR_FILENAME%.zip
    ) else (
        echo [경고] 압축 파일 생성에 실패했습니다.
    )
    echo.
)

echo ========================================
echo 빌드 완료!
echo ========================================
echo.
echo 다음 단계:
echo 1. %TAR_FILENAME% 파일을 NAS로 복사
echo 2. NAS에서 deploy_to_nas.sh 스크립트 실행
echo 3. http://[NAS_IP]:8000 으로 접속하여 확인
echo.
echo 빌드된 파일:
echo - %TAR_FILENAME% (Docker 이미지)
if exist %TAR_FILENAME%.zip (
    echo - %TAR_FILENAME%.zip (압축 파일)
)
echo.

pause
