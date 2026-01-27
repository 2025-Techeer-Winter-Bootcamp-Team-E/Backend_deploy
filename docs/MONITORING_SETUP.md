# 모니터링 설정 가이드 (Grafana + Prometheus)

## 개요
Django 애플리케이션을 Prometheus와 Grafana로 모니터링하는 설정 가이드입니다.

---

## 아키텍처

```
Django App (Backend)
    ↓ (메트릭 노출)
/metrics 엔드포인트
    ↓ (스크랩)
Prometheus (메트릭 수집 및 저장)
    ↓ (쿼리)
Grafana (시각화 및 대시보드)
```

---

## 구성 요소

### 1. Prometheus
- **역할**: 메트릭 수집 및 저장
- **포트**: 9090
- **URL**: http://localhost:9090
- **설정 파일**: `Backend/monitoring/prometheus/prometheus.yml`

### 2. Grafana
- **역할**: 메트릭 시각화 및 대시보드
- **포트**: 3000
- **URL**: http://localhost:3000
- **기본 로그인**: admin / admin123
- **설정 경로**: `Backend/monitoring/grafana/provisioning/`

---

## 설정 파일 구조

```
Backend/
├── monitoring/
│   ├── prometheus/
│   │   └── prometheus.yml          # Prometheus 설정
│   └── grafana/
│       └── provisioning/
│           ├── datasources/
│           │   └── prometheus.yml # Prometheus 데이터소스 설정
│           └── dashboards/
│               ├── dashboard.yml   # 대시보드 프로비저닝 설정
│               └── django-monitoring.json  # Django 모니터링 대시보드
```

---

## 시작하기

### 1. Docker Compose로 시작

```bash
cd Backend
docker compose up -d prometheus grafana
```

### 2. 서비스 확인

#### Prometheus
```bash
# Prometheus UI 접속
open http://localhost:9090

# 메트릭 확인
curl http://localhost:9090/api/v1/targets
```

#### Grafana
```bash
# Grafana UI 접속
open http://localhost:3000

# 로그인
# Username: admin
# Password: admin123
```

### 3. Django 메트릭 확인

```bash
# Django 메트릭 엔드포인트 확인
curl http://localhost:8000/metrics
```

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

### Django 캐시 메트릭
- `django_cache_hits_total`: 캐시 히트 수
- `django_cache_misses_total`: 캐시 미스 수

### Django 모델 메트릭
- `django_model_inserts_total`: 모델 INSERT 수
- `django_model_updates_total`: 모델 UPDATE 수
- `django_model_deletes_total`: 모델 DELETE 수

---

## Grafana 대시보드

### 자동 프로비저닝된 대시보드
- **Django Application Monitoring**: 기본 Django 애플리케이션 모니터링 대시보드

### 대시보드 패널
1. **HTTP Request Rate**: 초당 HTTP 요청 수
2. **HTTP Request Duration (p95)**: 95 백분위수 요청 지연 시간
3. **HTTP Status Codes**: 상태 코드별 요청 분포
4. **Active Database Connections**: 활성 DB 연결 수
5. **Total HTTP Requests**: 총 HTTP 요청 수 (통계)
6. **Error Rate**: 에러율 (5xx 상태 코드)
7. **API Endpoint Requests**: 엔드포인트별 요청 수 (테이블)

---

## 커스텀 메트릭 추가

### Django에서 커스텀 메트릭 정의

```python
# modules/search/metrics.py
from prometheus_client import Counter, Histogram

# 커스텀 카운터
shopping_research_requests = Counter(
    'shopping_research_requests_total',
    'Total shopping research requests',
    ['status']
)

# 커스텀 히스토그램
shopping_research_duration = Histogram(
    'shopping_research_duration_seconds',
    'Shopping research request duration',
    ['endpoint']
)

# 사용 예시
shopping_research_requests.labels(status='success').inc()
shopping_research_duration.labels(endpoint='/search/shopping-research/').observe(0.5)
```

### 뷰에서 메트릭 사용

```python
from modules.search.metrics import shopping_research_requests, shopping_research_duration
import time

class ShoppingResearchView(APIView):
    def post(self, request):
        start_time = time.time()
        try:
            # ... 로직 ...
            shopping_research_requests.labels(status='success').inc()
            return Response(...)
        except Exception as e:
            shopping_research_requests.labels(status='error').inc()
            raise
        finally:
            duration = time.time() - start_time
            shopping_research_duration.labels(
                endpoint='/search/shopping-research/'
            ).observe(duration)
```

---

## Prometheus 쿼리 예시

### HTTP 요청률
```promql
rate(django_http_requests_total[5m])
```

### 에러율 (5xx)
```promql
sum(rate(django_http_requests_total{status=~"5.."}[5m])) 
/ 
sum(rate(django_http_requests_total[5m]))
```

### 평균 응답 시간
```promql
rate(django_http_requests_latency_seconds_sum[5m]) 
/ 
rate(django_http_requests_latency_seconds_count[5m])
```

### 가장 많이 호출되는 엔드포인트
```promql
topk(10, sum(rate(django_http_requests_total[5m])) by (path))
```

---

## 알림 설정 (선택사항)

### Alertmanager 설정

`Backend/monitoring/prometheus/prometheus.yml`에 알림 규칙 추가:

```yaml
rule_files:
  - "/etc/prometheus/alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

### 알림 규칙 예시

```yaml
# Backend/monitoring/prometheus/alerts.yml
groups:
  - name: django_alerts
    rules:
      - alert: HighErrorRate
        expr: sum(rate(django_http_requests_total{status=~"5.."}[5m])) > 0.1
        for: 5m
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} requests/sec"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(django_http_requests_latency_seconds_bucket[5m])) > 1
        for: 5m
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }}s"
```

---

## 문제 해결

### Prometheus가 Django 메트릭을 수집하지 못함

1. **네트워크 확인**
   ```bash
   docker compose exec prometheus wget -O- http://backend:8000/metrics
   ```

2. **타겟 상태 확인**
   - Prometheus UI → Status → Targets
   - `django` job이 `UP` 상태인지 확인

3. **Django 메트릭 엔드포인트 확인**
   ```bash
   curl http://localhost:8000/metrics
   ```

### Grafana에서 데이터가 보이지 않음

1. **데이터소스 연결 확인**
   - Grafana UI → Configuration → Data Sources
   - Prometheus 데이터소스가 "Connected" 상태인지 확인

2. **대시보드 새로고침**
   - 대시보드 우측 상단의 새로고침 버튼 클릭

3. **시간 범위 확인**
   - 대시보드 우측 상단의 시간 선택기에서 적절한 범위 선택

### 메트릭이 너무 많아서 성능 저하

1. **스크랩 간격 조정**
   ```yaml
   # prometheus.yml
   global:
     scrape_interval: 30s  # 15s → 30s로 변경
   ```

2. **메트릭 필터링**
   - Prometheus 설정에서 특정 메트릭만 수집하도록 설정

---

## 참고 자료

- [Django Prometheus 문서](https://github.com/korfuri/django-prometheus)
- [Prometheus 공식 문서](https://prometheus.io/docs/)
- [Grafana 공식 문서](https://grafana.com/docs/)

---

## 접속 URL 요약

| 서비스 | URL | 기본 인증 |
|--------|-----|----------|
| Prometheus | http://localhost:9090 | 없음 |
| Grafana | http://localhost:3000 | admin / admin123 |
| Django Metrics | http://localhost:8000/metrics | 없음 |

---

## 다음 단계

1. **커스텀 메트릭 추가**: 비즈니스 로직별 메트릭 정의
2. **알림 설정**: Alertmanager를 통한 알림 구성
3. **대시보드 확장**: 추가 대시보드 및 패널 생성
4. **성능 최적화**: 메트릭 수집 간격 및 보관 기간 조정
