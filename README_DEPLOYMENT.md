# 재고관리 시스템 Docker 배포 가이드

이 가이드는 재고관리 시스템을 윈도우에서 Docker 이미지로 빌드하고 NAS에 배포하는 방법을 설명합니다.

## 📋 사전 요구사항

### 윈도우 환경
- Docker Desktop 설치 및 실행
- PowerShell 또는 Command Prompt

### NAS 환경
- Docker 설치 및 실행
- SSH 접속 가능
- 포트 8000 사용 가능

## 🚀 배포 과정

### 1단계: 윈도우에서 Docker 이미지 빌드

1. **프로젝트 디렉토리로 이동**
   ```cmd
   cd "C:\Users\User\Desktop\erp 웹"
   ```

2. **빌드 스크립트 실행**
   ```cmd
   build_docker_image.bat
   ```

3. **빌드 과정**
   - Docker 상태 확인
   - 기존 이미지 제거
   - 새 이미지 빌드
   - tar 파일로 저장
   - 압축 파일 생성 (선택사항)

4. **생성되는 파일**
   - `erp-system_latest.tar` - Docker 이미지 파일
   - `erp-system_latest.tar.zip` - 압축 파일 (선택사항)

### 2단계: NAS에 파일 전송

1. **파일 전송 방법**
   - SCP/SFTP 클라이언트 사용
   - NAS 웹 인터페이스 파일 업로드
   - 네트워크 드라이브 복사

2. **권장 전송 파일**
   - `erp-system_latest.tar` (압축 해제된 파일)
   - 또는 `erp-system_latest.tar.zip` (압축 파일)

### 3단계: NAS에서 배포

1. **SSH로 NAS 접속**
   ```bash
   ssh [NAS_사용자명]@[NAS_IP주소]
   ```

2. **파일이 있는 디렉토리로 이동**
   ```bash
   cd /path/to/erp-system
   ```

3. **배포 스크립트 실행**
   ```bash
   # 압축 해제된 파일인 경우
   ./deploy_to_nas.sh erp-system_latest.tar
   
   # 압축 파일인 경우
   ./deploy_to_nas.sh erp-system_latest.tar.zip
   ```

4. **배포 과정**
   - Docker 서비스 확인
   - 기존 컨테이너 중지/제거
   - 이미지 로드
   - 새 컨테이너 실행
   - 헬스체크 수행

## 🌐 접속 확인

배포 완료 후 다음 URL로 접속하여 확인:

- **로컬 접속**: http://localhost:8000
- **네트워크 접속**: http://[NAS_IP주소]:8000

## 📁 데이터 저장

- **데이터베이스**: `/volume1/docker/erp/data/` 디렉토리에 저장
- **로그 파일**: `/volume1/docker/erp/logs/` 디렉토리에 저장
- **자동 백업**: 컨테이너 재시작 시에도 데이터 유지

## 🔧 관리 명령어

### 컨테이너 관리
```bash
# 컨테이너 상태 확인
docker ps -f name=erp-system

# 로그 확인
docker logs erp-system

# 컨테이너 중지
docker stop erp-system

# 컨테이너 시작
docker start erp-system

# 컨테이너 재시작
docker restart erp-system
```

### 이미지 관리
```bash
# 이미지 목록 확인
docker images erp-system

# 이미지 제거
docker rmi erp-system:latest
```

## 🔄 업데이트 과정

1. **윈도우에서 새 이미지 빌드**
   ```cmd
   build_docker_image.bat
   ```

2. **NAS에 새 파일 전송**

3. **NAS에서 재배포**
   ```bash
   ./deploy_to_nas.sh erp-system_latest.tar
   ```

## ⚠️ 주의사항

1. **포트 충돌**: NAS의 8000번 포트가 사용 중이지 않은지 확인
2. **방화벽**: NAS 방화벽에서 8000번 포트 허용 설정
3. **자동 재시작**: 컨테이너는 `unless-stopped` 정책으로 자동 재시작됨
4. **데이터 백업**: `/volume1/docker/erp/data/` 디렉토리 정기 백업 권장

## 🐛 문제 해결

### 빌드 실패
- Docker Desktop이 실행 중인지 확인
- 디스크 공간 충분한지 확인
- 네트워크 연결 상태 확인

### 배포 실패
- Docker 서비스가 실행 중인지 확인
- 포트 8000이 사용 가능한지 확인
- 컨테이너 로그 확인: `docker logs erp-system`

### 접속 불가
- 방화벽 설정 확인
- 포트 포워딩 설정 확인
- 컨테이너 상태 확인: `docker ps -f name=erp-system`

## 📞 지원

문제가 발생하면 다음 정보와 함께 문의하세요:
- 운영체제 정보
- Docker 버전
- 오류 메시지
- 컨테이너 로그

---

**배포 완료 후 재고관리 시스템을 http://[NAS_IP]:8000 으로 접속하여 사용하세요!**
