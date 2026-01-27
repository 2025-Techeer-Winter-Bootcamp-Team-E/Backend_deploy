# 모니터링 설정

## 빠른 시작

### 1. 서비스 시작
```bash
docker compose up -d prometheus grafana
```

### 2. 접속
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin / admin123)

### 3. 대시보드 확인
Grafana에 로그인하면 "Django Application Monitoring" 대시보드가 자동으로 생성됩니다.

---

## 수집되는 메트릭

### Django HTTP 메트릭
- `django_http_requests_total`: 총 HTTP 요청 수
- `django_http_requests_latency_seconds`: 요청 지연 시간
- `django_http_responses_total`: HTTP 응답 수 (상태 코드별)

### Django 데이터베이스 메트릭
- `django_db_connections_active`: 활성 DB 연결 수
- `django_db_queries_total`: 총 DB 쿼리 수
- `django_db_query_duration_seconds`: DB 쿼리 실행 시간

---

## 파일 구조

```
monitoring/
├── prometheus/
│   └── prometheus.yml          # Prometheus 설정
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── prometheus.yml  # Prometheus 데이터소스
        └── dashboards/
            ├── dashboard.yml   # 대시보드 프로비저닝
            └── django-monitoring.json  # Django 모니터링 대시보드
```

---

## 자세한 문서

자세한 설정 및 사용 방법은 `Backend/docs/MONITORING_SETUP.md`를 참고하세요.
