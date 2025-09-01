# ERP 시스템

웹 기반 재고 관리 ERP 시스템입니다. FastAPI와 SQLite를 사용하여 구축되었습니다.

## 주요 기능

- **사용자 관리**: 회원가입, 로그인, 관리자 승인 시스템
- **재고 관리**: 제품 등록, 수정, 삭제, 재고 현황 조회
- **입출고 관리**: 입고/출고 처리, 거래 내역 관리
- **통계 및 분석**: 재고 현황, 거래 통계, 차트 시각화
- **관리자 기능**: 사용자 승인, 시스템 관리

## 기술 스택

- **Backend**: FastAPI, SQLAlchemy, SQLite
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **인증**: JWT (JSON Web Token)
- **차트**: Chart.js

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 관리자 계정 생성

```bash
python init_admin.py
```

### 3. 서버 실행

```bash
python main.py
```

또는

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 웹 브라우저에서 접속

```
http://localhost:8000
```

## 기본 관리자 계정

- **사용자명**: admin
- **비밀번호**: admin123
- **이메일**: admin@erp.com

> ⚠️ 보안을 위해 첫 로그인 후 비밀번호를 변경해주세요.

## 사용 방법

### 1. 관리자 설정
1. 관리자 계정으로 로그인
2. `/admin` 페이지에서 사용자 승인
3. 승인된 사용자는 시스템에 접근 가능

### 2. 재고 관리
1. `/inventory` 페이지에서 제품 등록
2. 제품명, 카테고리, 가격, 초기 재고 설정
3. 제품 목록에서 재고 현황 확인

### 3. 입출고 처리
1. `/stock/in` 페이지에서 입고 처리
2. `/stock/out` 페이지에서 출고 처리
3. 거래 내역은 자동으로 기록됨

### 4. 통계 확인
1. `/statistics` 페이지에서 재고 현황 확인
2. 카테고리별 재고 분포 확인
3. 최근 거래 내역 조회

## 프로젝트 구조

```
erp-system/
├── main.py              # 메인 FastAPI 애플리케이션
├── models.py            # 데이터베이스 모델
├── schemas.py           # Pydantic 스키마
├── database.py          # 데이터베이스 설정
├── auth.py              # 인증 및 권한 관리
├── init_admin.py        # 관리자 계정 초기화
├── requirements.txt     # Python 의존성
├── README.md           # 프로젝트 문서
├── templates/          # HTML 템플릿
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── admin.html
│   ├── inventory.html
│   ├── stock_in.html
│   ├── stock_out.html
│   └── statistics.html
└── static/             # 정적 파일
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

## API 엔드포인트

### 인증
- `POST /login` - 로그인
- `POST /register` - 회원가입

### 재고 관리
- `GET /inventory` - 재고 목록 조회
- `POST /inventory/add` - 제품 추가

### 입출고
- `POST /stock/in` - 입고 처리
- `POST /stock/out` - 출고 처리

### 관리자
- `GET /admin` - 관리자 페이지
- `POST /admin/approve/{user_id}` - 사용자 승인

### 통계
- `GET /statistics` - 통계 데이터 조회

## 보안 고려사항

1. **JWT 토큰**: 인증된 사용자만 접근 가능
2. **관리자 승인**: 새 사용자는 관리자 승인 필요
3. **비밀번호 해싱**: bcrypt를 사용한 안전한 비밀번호 저장
4. **입력 검증**: Pydantic을 사용한 데이터 검증

## 개발 및 배포

### 개발 모드
```bash
uvicorn main:app --reload
```

### 프로덕션 배포
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 데이터베이스 백업
SQLite 데이터베이스 파일(`erp_system.db`)을 정기적으로 백업하세요.

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 지원

문제가 발생하거나 기능 요청이 있으시면 이슈를 생성해주세요.
