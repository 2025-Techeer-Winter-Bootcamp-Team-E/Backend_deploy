# 기술 스택 버전 명세

이 문서는 프로젝트에서 사용된 언어, 프레임워크, 라이브러리의 버전을 명시합니다.

---

## 언어

| 구분 | 버전 | 비고 |
|------|------|------|
| Python | 3.11 | Docker 베이스 이미지 |

---

## 핵심 프레임워크

| 패키지 | 버전 | 설명 |
|--------|------|------|
| Django | 5.0.x | 웹 프레임워크 |
| Django REST Framework | 3.14.0+ | REST API 프레임워크 |
| Celery | 5.3.4+ | 비동기 태스크 큐 |

---

## 데이터베이스 및 캐시

| 서비스 | 버전 | 설명 |
|--------|------|------|
| PostgreSQL | 16 | 메인 데이터베이스 (pgvector/pgvector:pg16) |
| pgvector | 0.2.4+ | 벡터 검색 확장 |
| Redis | 7 (Alpine) | 캐시 및 Celery 결과 저장소 |
| RabbitMQ | 3.12 (Alpine) | 메시지 브로커 |

---

## Python 패키지

### Django 관련

| 패키지 | 버전 | 설명 |
|--------|------|------|
| django-cors-headers | 4.3.0+ | CORS 처리 |
| django-filter | 23.5+ | 쿼리 필터링 |
| django-celery-beat | 2.5.0+ | Celery 스케줄러 |
| django-celery-results | 2.5.1+ | Celery 결과 저장 |
| django-redis | 5.4.0+ | Redis 캐시 백엔드 |
| django-storages | 1.14.2+ | S3 스토리지 백엔드 |
| django-prometheus | 2.3.1+ | Prometheus 메트릭 |

### API 문서화

| 패키지 | 버전 | 설명 |
|--------|------|------|
| drf-spectacular | 0.27.0+ | OpenAPI 스키마 생성 (Swagger) |
| drf-spectacular-sidecar | 2024.1.1+ | Swagger UI 정적 파일 |

### 인증

| 패키지 | 버전 | 설명 |
|--------|------|------|
| djangorestframework-simplejwt | 5.3.1+ | JWT 인증 |
| PyJWT | 2.8.0+ | JWT 라이브러리 |

### 데이터베이스 드라이버

| 패키지 | 버전 | 설명 |
|--------|------|------|
| psycopg2-binary | 2.9.9+ | PostgreSQL 드라이버 |
| pgvector | 0.2.4+ | pgvector Python 클라이언트 |
| redis | 5.0.1+ | Redis Python 클라이언트 |

### 메시지 브로커

| 패키지 | 버전 | 설명 |
|--------|------|------|
| pika | 1.3.2+ | RabbitMQ 클라이언트 |
| kombu | 5.3.4+ | 메시징 라이브러리 |

### AI 서비스

| 패키지 | 버전 | 설명 |
|--------|------|------|
| openai | 1.10.0+ | OpenAI API 클라이언트 |
| google-generativeai | 0.3.2+ | Google Gemini API 클라이언트 |

### 서버

| 패키지 | 버전 | 설명 |
|--------|------|------|
| gunicorn | 21.2.0+ | WSGI 서버 |
| uvicorn | 0.27.0+ | ASGI 서버 |

### 유틸리티

| 패키지 | 버전 | 설명 |
|--------|------|------|
| pydantic | 2.5.3+ | 데이터 검증 |
| python-decouple | 3.8+ | 환경 변수 관리 |
| python-dotenv | 1.0.0+ | .env 파일 로드 |
| boto3 | 1.34.0+ | AWS SDK |
| Pillow | 10.2.0+ | 이미지 처리 |
| python-slugify | 8.0.1+ | 슬러그 생성 |

### 모니터링

| 패키지 | 버전 | 설명 |
|--------|------|------|
| flower | 2.0.1+ | Celery 모니터링 UI |
| sentry-sdk | 1.39.1+ | 에러 트래킹 |

---

## 인프라 (Docker)

| 서비스 | 이미지 | 버전 |
|--------|--------|------|
| PostgreSQL + pgvector | pgvector/pgvector | pg16 |
| Redis | redis | 7-alpine |
| RabbitMQ | rabbitmq | 3.12-management-alpine |
| MinIO | minio/minio | latest |
| Prometheus | prom/prometheus | v2.47.0 |
| Grafana | grafana/grafana | 10.1.0 |

---

## Docker Compose

| 항목 | 버전 |
|------|------|
| docker-compose.yml | 3.9 |

---

## 버전 업데이트 정책

### Semantic Versioning

- **Major (X.0.0)**: 호환성 깨지는 변경 - 팀 논의 필요
- **Minor (0.X.0)**: 새로운 기능 추가 - 테스트 후 적용
- **Patch (0.0.X)**: 버그 수정 - 바로 적용 가능

### 권장 업데이트 주기

| 구분 | 주기 | 담당 |
|------|------|------|
| 보안 패치 | 즉시 | 전체 팀 |
| Django/DRF | 분기별 | 인프라 담당 |
| Python 패키지 | 월별 | 각 모듈 담당 |
| Docker 이미지 | 분기별 | 인프라 담당 |

---

## 호환성 매트릭스

```
Python 3.11
    └── Django 5.0.x
            ├── DRF 3.14.x
            ├── Celery 5.3.x
            │       └── RabbitMQ 3.12.x
            │       └── Redis 7.x
            ├── PostgreSQL 16
            │       └── pgvector 0.2.x
            └── SimpleJWT 5.3.x
```

---

## 참고 링크

- [Django Release Notes](https://docs.djangoproject.com/en/5.0/releases/)
- [DRF Changelog](https://www.django-rest-framework.org/community/release-notes/)
- [Celery Changelog](https://docs.celeryq.dev/en/stable/changelog.html)
- [PostgreSQL Release Notes](https://www.postgresql.org/docs/16/release.html)
- [pgvector GitHub](https://github.com/pgvector/pgvector)

---

*마지막 업데이트: 2025년 1월*
