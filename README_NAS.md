# ERP 시스템 - NAS 배포 가이드

## 개요
이 ERP 시스템은 NAS 환경에서 Docker를 사용하여 실행할 수 있는 웹 기반 재고 관리 시스템입니다.

## NAS 환경 요구사항
- Docker 및 Docker Compose 설치된 NAS
- 최소 2GB RAM
- 최소 5GB 저장 공간
- 네트워크 접근 가능한 환경

## 파일 구조
```
erp-system/
├── Dockerfile                 # Docker 이미지 빌드 파일
├── docker-compose.yml         # Docker Compose 설정
├── .dockerignore             # Docker 빌드 시 제외 파일
├── start.sh                  # 시스템 시작 스크립트
├── stop.sh                   # 시스템 중지 스크립트
├── restart.sh                # 시스템 재시작 스크립트
├── status.sh                 # 시스템 상태 확인 스크립트
├── backup.sh                 # 백업 스크립트
├── restore.sh                # 복원 스크립트
├── logs.sh                   # 로그 확인 스크립트
├── /volume1/docker/erp/data/     # 데이터베이스 저장 디렉토리
├── /volume1/docker/erp/logs/     # 로그 파일 저장 디렉토리
└── /volume1/docker/erp/backups/  # 백업 파일 저장 디렉토리
```

## 빠른 시작

### 1. 파일 업로드
NAS에 모든 파일을 업로드합니다.

### 2. 터미널 접속
NAS의 SSH 또는 터미널에 접속합니다.

### 3. 실행 권한 부여
```bash
chmod +x *.sh
```

### 4. 시스템 시작
```bash
./start.sh
```

## 스크립트 사용법

### 🚀 start.sh - 시스템 시작
```bash
./start.sh
```
- Docker 및 Docker Compose 설치 확인
- 필요한 디렉토리 생성
- 기존 컨테이너 정리 옵션
- 시스템 시작 및 헬스체크

### 🛑 stop.sh - 시스템 중지
```bash
./stop.sh
```
- 서비스만 중지 (데이터 보존)
- 서비스 중지 + 볼륨 삭제 (데이터 삭제)
- 완전 정리 (서비스 + 볼륨 + 이미지 삭제)

### 🔄 restart.sh - 시스템 재시작
```bash
./restart.sh
```
- 일반 재시작 (빠른 재시작)
- 완전 재시작 (이미지 재빌드)
- 데이터 초기화 후 재시작

### 📊 status.sh - 상태 확인
```bash
./status.sh
```
- 서비스 실행 상태
- 리소스 사용량
- 데이터베이스 상태
- 포트 사용 상태
- 최근 로그

### 💾 backup.sh - 백업
```bash
./backup.sh
```
- 데이터베이스만 백업
- 전체 백업 (데이터베이스 + 로그)
- Docker 이미지 포함 백업
- 오래된 백업 자동 정리

### 🔄 restore.sh - 복원
```bash
./restore.sh
```
- 백업 파일 목록 표시
- 데이터베이스만 복원
- 전체 복원
- Docker 이미지 포함 복원

### 📝 logs.sh - 로그 확인
```bash
./logs.sh
```
- 실시간 로그 (tail -f)
- 최근 로그 (마지막 50줄)
- 전체 로그
- 오류 로그만
- 특정 시간대 로그
- 로그 파일 다운로드

## 접속 정보
- **URL**: `http://[NAS_IP]:8000`
- **관리자 계정**:
  - 사용자명: `admin`
  - 비밀번호: `admin123`
  - 이메일: `admin@erp.com`

## 데이터 영속성
- **데이터베이스**: `/volume1/docker/erp/data/erp_system.db`
- **로그**: `/volume1/docker/erp/logs/` 디렉토리
- **백업**: `/volume1/docker/erp/backups/` 디렉토리
- 컨테이너 재시작 시에도 데이터 유지

## 자동화 설정

### Cron을 사용한 자동 백업
```bash
# crontab 편집
crontab -e

# 매일 새벽 2시에 백업 실행
0 2 * * * /path/to/erp-system/backup.sh

# 매주 일요일 새벽 3시에 오래된 백업 정리
0 3 * * 0 find /path/to/erp-system/backups -name "erp_backup_*" -type f -mtime +30 -delete
```

### 시스템 부팅 시 자동 시작
```bash
# /etc/rc.local 또는 systemd 서비스로 설정
/path/to/erp-system/start.sh
```

## 문제 해결

### 1. 포트 충돌
```bash
# 포트 사용 확인
netstat -tuln | grep :8000

# docker-compose.yml에서 포트 변경
ports:
  - "8001:8000"  # 8001 포트로 변경
```

### 2. 권한 문제
```bash
# 실행 권한 부여
chmod +x *.sh

# 디렉토리 권한 설정
chmod 755 data logs backups
```

### 3. 메모리 부족
```bash
# Docker 메모리 제한 설정
# docker-compose.yml에 추가
deploy:
  resources:
    limits:
      memory: 1G
```

### 4. 디스크 공간 부족
```bash
# 디스크 사용량 확인
df -h

# 오래된 백업 파일 정리
find backups -name "erp_backup_*" -type f -mtime +7 -delete
```

## 보안 설정

### 1. 방화벽 설정
```bash
# 8000 포트만 허용
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

### 2. 관리자 비밀번호 변경
1. 관리자로 로그인
2. 프로필 설정에서 비밀번호 변경

### 3. HTTPS 설정 (권장)
- Nginx 리버스 프록시 설정
- Let's Encrypt SSL 인증서 사용

## 모니터링

### 1. 시스템 리소스 모니터링
```bash
# CPU 및 메모리 사용량
./status.sh

# 실시간 모니터링
watch -n 5 './status.sh'
```

### 2. 로그 모니터링
```bash
# 실시간 로그 확인
./logs.sh

# 오류 로그만 확인
docker-compose logs | grep -i error
```

## 업데이트

### 1. 코드 업데이트
```bash
# 새 코드 다운로드 후
./restart.sh
# 옵션 2 (완전 재시작) 선택
```

### 2. 데이터베이스 마이그레이션
```bash
# 백업 생성
./backup.sh

# 업데이트 실행
./restart.sh

# 문제 발생 시 복원
./restore.sh
```

## 지원 및 문의
- 시스템 문제 발생 시 `./status.sh`와 `./logs.sh`로 상태 확인
- 백업은 정기적으로 수행 권장
- 중요한 데이터는 별도 위치에 추가 백업 권장
