# ERP 시스템 - Docker 배포 가이드

## 개요
이 ERP 시스템은 회원 가입 시 관리자 승인이 필요한 웹 기반 재고 관리 시스템입니다.

## 주요 기능
- **관리자 승인 시스템**: 회원 가입 후 관리자 승인 필요
- **재고 관리**: 제품 입고/출고 관리
- **거래처 관리**: 입고처/출고처 관리
- **LOT 관리**: 제품별 LOT 번호 추적
- **안전 재고 알림**: 3단계 안전재고 시스템
- **거래 내역 관리**: 필터링 및 엑셀 다운로드

## Docker 배포

### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd erp-system
```

### 2. Docker Compose로 실행
```bash
# 백그라운드에서 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

### 3. 접속
- 웹 브라우저에서 `http://localhost:8000` 접속
- 기본 관리자 계정:
  - 사용자명: `admin`
  - 비밀번호: `admin123`
  - 이메일: `admin@erp.com`

## 사용법

### 1. 관리자 로그인
1. `http://localhost:8000` 접속
2. 관리자 계정으로 로그인
3. **보안을 위해 첫 로그인 후 비밀번호 변경 권장**

### 2. 사용자 승인
1. 관리자 페이지(`/admin`) 접속
2. 승인 대기 중인 사용자 목록 확인
3. 사용자 승인 버튼 클릭

### 3. 일반 사용자 회원가입
1. 회원가입 페이지에서 정보 입력
2. 승인 대기 페이지로 이동
3. 관리자 승인 후 로그인 가능

## 데이터 영속성
- 데이터베이스 파일은 `./data/erp_system.db`에 저장
- 컨테이너 재시작 시에도 데이터 유지
- 로그 파일은 `./logs/` 디렉토리에 저장

## 환경 변수
- `DB_DIR`: 데이터베이스 저장 경로 (기본값: `/app/data`)
- `PYTHONPATH`: Python 경로 (기본값: `/app`)
- `PYTHONUNBUFFERED`: Python 출력 버퍼링 비활성화

## 헬스체크
- 컨테이너는 30초마다 헬스체크 수행
- `/login` 엔드포인트로 서비스 상태 확인

## 문제 해결

### 1. 포트 충돌
```bash
# 8000 포트가 사용 중인 경우 docker-compose.yml에서 포트 변경
ports:
  - "8001:8000"  # 8001 포트로 변경
```

### 2. 데이터베이스 초기화
```bash
# 데이터 디렉토리 삭제 후 재시작
rm -rf ./data
docker-compose restart
```

### 3. 로그 확인
```bash
# 컨테이너 로그 확인
docker-compose logs erp-system

# 실시간 로그 모니터링
docker-compose logs -f erp-system
```

## 보안 주의사항
1. **기본 관리자 비밀번호 변경 필수**
2. 프로덕션 환경에서는 SECRET_KEY 변경
3. HTTPS 사용 권장
4. 정기적인 데이터베이스 백업

## 개발 모드
```bash
# 개발 모드로 실행 (코드 변경 시 자동 재시작)
docker-compose up --build
```

## 중지 및 정리
```bash
# 서비스 중지
docker-compose down

# 볼륨까지 삭제 (데이터 삭제됨)
docker-compose down -v

# 이미지까지 삭제
docker-compose down --rmi all
```
