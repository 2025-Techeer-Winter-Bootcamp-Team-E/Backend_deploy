# E-commerce Backend 아키텍처 문서

## 개요

이 프로젝트는 **모듈러 모노리스(Modular Monolith)** 아키텍처를 사용합니다.
5명 팀에 적합하도록 설계되었으며, 각 팀원이 독립적인 모듈을 담당합니다.

---

## 1. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Web/Mobile)                      │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ HTTP/HTTPS
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Django REST Framework                         │
│                    (Gunicorn + Nginx)                            │
├─────────────────────────────────────────────────────────────────┤
│    modules/users    │   modules/products   │   modules/orders   │
│    ───────────────  │   ────────────────   │   ───────────────  │
│    - models.py      │   - models.py        │   - models.py      │
│    - services.py    │   - services.py      │   - services.py    │
│    - views.py       │   - views.py         │   - views.py       │
├─────────────────────────────────────────────────────────────────┤
│  modules/categories │   modules/search     │ modules/price_pred │
│  ─────────────────  │   ──────────────     │ ────────────────── │
│  - 카테고리 관리     │   - 키워드/시맨틱 검색 │ - 가격 예측 AI     │
│  - 계층 구조        │   - 검색 히스토리     │ - 가격 히스토리    │
│  - 속성 관리        │   - 인기 검색어       │ - 트렌드 분석      │
├─────────────────────────────────────────────────────────────────┤
│                         shared/                                  │
│    exceptions.py | permissions.py | utils.py | cache.py         │
│    ai_clients.py | storage.py | health/                         │
└───────────┬─────────────────┬─────────────────┬─────────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
┌───────────────┐   ┌─────────────────┐   ┌──────────────┐
│  PostgreSQL   │   │     Redis       │   │  RabbitMQ    │
│  + pgvector   │   │    (Cache)      │   │  (Celery)    │
└───────────────┘   └─────────────────┘   └──────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│    ┌──────────┐    ┌──────────┐    ┌──────────────────┐         │
│    │  MinIO   │    │ OpenAI   │    │ Google Gemini    │         │
│    │  (S3)    │    │ Embedding│    │                  │         │
│    └──────────┘    └──────────┘    └──────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 프로젝트 구조

```
backend/
├── config/                     # Django 설정
│   ├── settings/
│   │   ├── base.py            # 공통 설정
│   │   ├── dev.py             # 개발 환경
│   │   └── prod.py            # 운영 환경
│   ├── celery.py              # Celery 설정
│   ├── urls.py                # URL 라우팅
│   ├── wsgi.py
│   └── asgi.py
│
├── modules/                    # 모듈러 모노리스
│   ├── users/                 # 사용자 모듈
│   │   ├── models.py          # Django ORM 모델
│   │   ├── services.py        # 비즈니스 로직
│   │   ├── views.py           # API 뷰
│   │   ├── serializers.py     # DRF 시리얼라이저
│   │   ├── urls.py            # URL 패턴
│   │   ├── admin.py           # Django Admin
│   │   ├── tasks.py           # Celery 태스크
│   │   ├── exceptions.py      # 모듈 예외
│   │   └── tests/             # 테스트
│   │
│   ├── products/              # 상품 모듈
│   │   └── (동일 구조)
│   │
│   ├── orders/                # 주문 모듈
│   │   └── (동일 구조)
│   │
│   ├── categories/            # 카테고리 모듈
│   │   └── (동일 구조)
│   │
│   ├── search/                # 검색 모듈
│   │   └── (동일 구조)
│   │
│   └── price_prediction/      # 가격 예측 모듈
│       └── (동일 구조)
│
├── shared/                     # 공유 모듈
│   ├── exceptions.py          # 공통 예외 + 핸들러
│   ├── permissions.py         # DRF 권한 클래스
│   ├── utils.py               # 유틸리티 함수
│   ├── cache.py               # Redis 캐시
│   ├── ai_clients.py          # OpenAI, Gemini
│   ├── storage.py             # S3/MinIO 스토리지
│   └── health/                # 헬스 체크
│       ├── views.py
│       └── urls.py
│
├── tests/                      # 통합 테스트
├── scripts/                    # 유틸리티 스크립트
├── monitoring/                 # Prometheus, Grafana
├── docs/                       # 문서
├── docker-compose.yml
├── Dockerfile
└── requirements/
    ├── base.txt
    ├── dev.txt
    └── prod.txt
```

---

## 3. 모듈 간 통신 규칙

### 핵심 규칙

```python
# ✅ 좋은 예: Service를 통해 호출
from modules.products.services import ProductService

class OrderService:
    def __init__(self):
        self.product_service = ProductService()

    def create_order(self, user_id, cart_items, ...):
        # 다른 모듈의 데이터는 Service로 접근
        product = self.product_service.get_product_by_id(product_id)
        if not self.product_service.check_stock(product_id, quantity):
            raise InsufficientStockError(...)

# ❌ 나쁜 예: 다른 모듈 Model 직접 import
from modules.products.models import ProductModel  # 금지!
```

### 모듈별 Public Interface

각 모듈의 `services.py`에서 다른 모듈이 사용할 수 있는 public 메서드:

**UserService:**
- `get_user_by_id(user_id)` - ID로 사용자 조회
- `get_user_by_email(email)` - 이메일로 사용자 조회

**ProductService:**
- `get_product_by_id(product_id)` - 상품 조회
- `get_products_by_ids(product_ids)` - 다중 상품 조회
- `check_stock(product_id, quantity)` - 재고 확인
- `decrease_stock(product_id, quantity)` - 재고 감소
- `increase_stock(product_id, quantity)` - 재고 증가

**OrderService:**
- `get_order_by_id(order_id)` - 주문 조회
- `get_user_orders(user_id)` - 사용자 주문 목록

**CategoryService:**
- `get_category_by_id(category_id)` - 카테고리 조회
- `get_category_by_slug(slug)` - 슬러그로 카테고리 조회
- `get_subcategories(parent_id)` - 하위 카테고리 조회
- `get_category_tree()` - 전체 카테고리 트리
- `get_category_ancestors(category_id)` - 상위 카테고리 (브레드크럼)

**SearchService:**
- `search_products(query, search_type, filters)` - 상품 검색
- `get_popular_searches(limit)` - 인기 검색어
- `get_search_suggestions(query)` - 검색어 자동완성

**PricePredictionService:**
- `get_prediction_by_product(product_id)` - 상품 가격 예측 조회
- `get_predictions_for_product(product_id, days)` - N일간 예측
- `get_price_trend(product_id, days)` - 가격 트렌드 분석

---

## 4. 파일 간 통신 흐름 (상세)

### 4.1 모듈 내부 파일 역할 및 의존성

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           modules/{module}/                              │
│                                                                          │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐           │
│  │   urls.py    │─────>│   views.py   │─────>│ services.py  │           │
│  │  (라우팅)     │      │  (API 핸들러) │      │ (비즈니스 로직)│           │
│  └──────────────┘      └──────┬───────┘      └──────┬───────┘           │
│                               │                      │                   │
│                               ▼                      ▼                   │
│                        ┌──────────────┐      ┌──────────────┐           │
│                        │serializers.py│      │  models.py   │           │
│                        │ (직렬화/검증) │      │  (DB 모델)    │           │
│                        └──────────────┘      └──────────────┘           │
│                                                      │                   │
│  ┌──────────────┐      ┌──────────────┐             │                   │
│  │   admin.py   │─────>│  models.py   │<────────────┘                   │
│  │ (관리자 UI)   │      └──────────────┘                                 │
│  └──────────────┘                                                        │
│                                                                          │
│  ┌──────────────┐      ┌──────────────┐                                 │
│  │   tasks.py   │─────>│ services.py  │  (Celery 비동기 작업)            │
│  └──────────────┘      └──────────────┘                                 │
│                                                                          │
│  ┌──────────────┐                                                        │
│  │exceptions.py │  (모듈 전용 예외 클래스)                                │
│  └──────────────┘                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 요청 처리 흐름 (Request Flow)

#### 예시 1: 회원가입 API

```
Client                                    Django Backend
  │                                            │
  │  POST /api/v1/users/register/              │
  │  { email, username, password }             │
  │ ──────────────────────────────────────────>│
  │                                            │
  │         ┌──────────────────────────────────┼───────────────────────────┐
  │         │  config/urls.py                  │                           │
  │         │  path('api/v1/users/', include('modules.users.urls'))        │
  │         └──────────────────────────────────┼───────────────────────────┘
  │                                            │
  │         ┌──────────────────────────────────┼───────────────────────────┐
  │         │  modules/users/urls.py           │                           │
  │         │  path('register/', RegisterView.as_view())                   │
  │         └──────────────────────────────────┼───────────────────────────┘
  │                                            │
  │         ┌──────────────────────────────────┼───────────────────────────┐
  │         │  modules/users/views.py          │                           │
  │         │                                  │                           │
  │         │  class RegisterView(APIView):    │                           │
  │         │      def post(self, request):    │                           │
  │         │          # 1. 요청 데이터 검증    │                           │
  │         │          serializer = UserCreateSerializer(data=request.data)│
  │         │          serializer.is_valid(raise_exception=True)           │
  │         │                                  │                           │
  │         │          # 2. 서비스 호출        │                           │
  │         │          user = user_service.register_user(...)              │
  │         │                                  │                           │
  │         │          # 3. 응답 반환          │                           │
  │         │          return Response(UserSerializer(user).data, 201)     │
  │         └──────────────────────────────────┼───────────────────────────┘
  │                                            │
  │         ┌──────────────────────────────────┼───────────────────────────┐
  │         │  modules/users/serializers.py    │                           │
  │         │                                  │                           │
  │         │  class UserCreateSerializer:     │                           │
  │         │      email = EmailField()        │                           │
  │         │      username = CharField()      │                           │
  │         │      password = CharField()      │  ← 입력 데이터 검증        │
  │         └──────────────────────────────────┼───────────────────────────┘
  │                                            │
  │         ┌──────────────────────────────────┼───────────────────────────┐
  │         │  modules/users/services.py       │                           │
  │         │                                  │                           │
  │         │  class UserService:              │                           │
  │         │      def register_user(self, email, username, password):     │
  │         │          # 1. 중복 검사          │                           │
  │         │          if UserModel.objects.filter(email=email).exists():  │
  │         │              raise UserAlreadyExistsError(...)               │
  │         │                                  │                           │
  │         │          # 2. 사용자 생성        │                           │
  │         │          user = UserModel.objects.create_user(...)           │
  │         │          return user             │                           │
  │         └──────────────────────────────────┼───────────────────────────┘
  │                                            │
  │         ┌──────────────────────────────────┼───────────────────────────┐
  │         │  modules/users/models.py         │                           │
  │         │                                  │                           │
  │         │  class UserModel(AbstractBaseUser):                          │
  │         │      email, username, password   │  ← DB 저장                │
  │         └──────────────────────────────────┼───────────────────────────┘
  │                                            │
  │<───────────────────────────────────────────│
  │  201 Created                               │
  │  { id, email, username, ... }              │
  │                                            │
```

#### 예시 2: 주문 생성 (모듈 간 통신)

```
Client                                    Django Backend
  │                                            │
  │  POST /api/v1/orders/                      │
  │  { shipping_info: {...} }                  │
  │ ──────────────────────────────────────────>│
  │                                            │
  │    ┌───────────────────────────────────────┼─────────────────────────────┐
  │    │  modules/orders/views.py              │                             │
  │    │                                       │                             │
  │    │  class OrderListCreateView(APIView):  │                             │
  │    │      def post(self, request):         │                             │
  │    │          order = order_service.create_order_from_cart(              │
  │    │              user_id=request.user.id, │                             │
  │    │              **shipping_info          │                             │
  │    │          )                            │                             │
  │    └───────────────────────────────────────┼─────────────────────────────┘
  │                                            │
  │    ┌───────────────────────────────────────┼─────────────────────────────┐
  │    │  modules/orders/services.py           │                             │
  │    │                                       │                             │
  │    │  class OrderService:                  │                             │
  │    │      def __init__(self):              │                             │
  │    │          self.cart_service = CartService()                          │
  │    │                                       │                             │
  │    │      def create_order_from_cart(self, user_id, ...):                │
  │    │                                       │                             │
  │    │          # 1. 장바구니 조회 (같은 모듈) │                             │
  │    │          cart = self.cart_service.get_cart(user_id)                 │
  │    │                                       │                             │
  │    │          # 2. 주문 생성               │                             │
  │    │          order = OrderModel.objects.create(...)                     │
  │    │                                       │                             │
  │    │          # 3. 상품 재고 차감 (다른 모듈 호출!)                        │
  │    │          from modules.products.services import ProductService       │
  │    │          product_service = ProductService()                         │
  │    │          for item in cart.items.all():│                             │
  │    │              product_service.decrease_stock(                        │
  │    │                  item.product_id,     │                             │
  │    │                  item.quantity        │                             │
  │    │              )                        │                             │
  │    │                                       │                             │
  │    │          # 4. 장바구니 비우기          │                             │
  │    │          self.cart_service.clear_cart(user_id)                      │
  │    │                                       │                             │
  │    │          return order                 │                             │
  │    └───────────────────────────────────────┼─────────────────────────────┘
  │                                            │
  │    ┌───────────────────────────────────────┼─────────────────────────────┐
  │    │  modules/products/services.py         │  ← 다른 모듈!               │
  │    │                                       │                             │
  │    │  class ProductService:                │                             │
  │    │      def decrease_stock(self, product_id, quantity):                │
  │    │          product = ProductModel.objects.get(id=product_id)          │
  │    │          if product.stock_quantity < quantity:                      │
  │    │              raise InsufficientStockError(...)                      │
  │    │          product.stock_quantity -= quantity                         │
  │    │          product.save()               │                             │
  │    └───────────────────────────────────────┼─────────────────────────────┘
  │                                            │
  │<───────────────────────────────────────────│
  │  201 Created                               │
  │  { order_number, status, items, ... }      │
```

### 4.3 비동기 작업 흐름 (Celery)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              동기 요청 처리                                  │
│                                                                             │
│  Client ──> views.py ──> services.py ──> models.py ──> Database            │
│                              │                                              │
│                              │  tasks.delay(product_id)  (비동기 작업 예약)  │
│                              ▼                                              │
│                        ┌──────────┐                                         │
│                        │ RabbitMQ │  메시지 큐                               │
│                        └────┬─────┘                                         │
│                             │                                               │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              비동기 작업 처리 (Celery Worker)                │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  modules/products/tasks.py                                           │   │
│  │                                                                      │   │
│  │  @shared_task                                                        │   │
│  │  def generate_product_embedding(product_id):                         │   │
│  │      # 1. DB에서 상품 조회                                            │   │
│  │      product = ProductModel.objects.get(id=product_id)               │   │
│  │                                                                      │   │
│  │      # 2. shared 모듈의 AI 클라이언트 사용                             │   │
│  │      from shared.ai_clients import OpenAIClient                      │   │
│  │      client = OpenAIClient()                                         │   │
│  │                                                                      │   │
│  │      # 3. 임베딩 생성                                                 │   │
│  │      text = f"{product.name}. {product.description}"                 │   │
│  │      embedding = client.create_embedding(text)                       │   │
│  │                                                                      │   │
│  │      # 4. DB 업데이트                                                 │   │
│  │      product.embedding = embedding                                   │   │
│  │      product.save()                                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│                     ┌──────────────┐                                        │
│                     │   OpenAI     │  외부 API 호출                          │
│                     │   API        │                                        │
│                     └──────────────┘                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.4 모듈 간 의존성 다이어그램

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│                          ┌─────────────┐                                 │
│                          │   shared/   │                                 │
│                          │             │                                 │
│                          │ exceptions  │                                 │
│                          │ permissions │                                 │
│                          │ cache       │                                 │
│                          │ ai_clients  │                                 │
│                          │ storage     │                                 │
│                          └──────┬──────┘                                 │
│                                 │                                        │
│              ┌──────────────────┼──────────────────┐                     │
│              │                  │                  │                     │
│              ▼                  ▼                  ▼                     │
│     ┌─────────────┐    ┌─────────────┐    ┌─────────────┐               │
│     │   users/    │    │  products/  │    │   orders/   │               │
│     │             │    │             │    │             │               │
│     │ UserService │    │ProductService│   │OrderService │               │
│     │             │    │             │    │ CartService │               │
│     └──────┬──────┘    └──────┬──────┘    └──────┬──────┘               │
│            │                  │                  │                       │
│            │                  │                  │                       │
│            │                  │     ┌────────────┘                       │
│            │                  │     │                                    │
│            │                  │     │  orders → products                 │
│            │                  │<────┘  (재고 확인/차감)                   │
│            │                  │                                          │
│            │                  │     ┌────────────┐                       │
│            │                  │     │            │                       │
│            │                  │     │  orders → users                    │
│            └──────────────────┼─────┘  (사용자 검증)                      │
│                               │                                          │
│                               │                                          │
│            ※ 순환 의존성 금지!  │                                          │
│            products ──X──> orders (금지)                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.5 장바구니 → 주문 전체 흐름

```
Step 1: 장바구니 추가
─────────────────────────────────────────────────────────────────────────────
POST /api/v1/orders/cart/
{ product_id: "xxx", quantity: 2 }

  orders/views.py          orders/services.py       products/services.py
       │                         │                         │
       │  add_item()             │                         │
       │────────────────────────>│                         │
       │                         │  get_product_by_id()    │
       │                         │────────────────────────>│
       │                         │<────────────────────────│
       │                         │  { name, price, ... }   │
       │                         │                         │
       │                         │  CartItemModel.create() │
       │                         │  (product_id, quantity, │
       │                         │   product_name, price)  │
       │<────────────────────────│                         │
       │  cart data              │                         │


Step 2: 주문 생성
─────────────────────────────────────────────────────────────────────────────
POST /api/v1/orders/
{ shipping_info: {...} }

  orders/views.py          orders/services.py       products/services.py
       │                         │                         │
       │  create_order_from_cart()                         │
       │────────────────────────>│                         │
       │                         │                         │
       │                         │  [1] 장바구니 조회       │
       │                         │  cart = get_cart()      │
       │                         │                         │
       │                         │  [2] 주문 생성          │
       │                         │  OrderModel.create()    │
       │                         │                         │
       │                         │  [3] 재고 차감          │
       │                         │  for item in cart:      │
       │                         │    decrease_stock()     │
       │                         │────────────────────────>│
       │                         │<────────────────────────│
       │                         │                         │
       │                         │  [4] 장바구니 비우기     │
       │                         │  clear_cart()           │
       │                         │                         │
       │<────────────────────────│                         │
       │  order data             │                         │


Step 3: 주문 취소 (재고 복구)
─────────────────────────────────────────────────────────────────────────────
DELETE /api/v1/orders/{order_id}/

  orders/views.py          orders/services.py       products/services.py
       │                         │                         │
       │  cancel_order()         │                         │
       │────────────────────────>│                         │
       │                         │  [1] 주문 상태 확인      │
       │                         │  order = get_order()    │
       │                         │                         │
       │                         │  [2] 재고 복구          │
       │                         │  for item in order:     │
       │                         │    increase_stock()     │
       │                         │────────────────────────>│
       │                         │<────────────────────────│
       │                         │                         │
       │                         │  [3] 상태 변경          │
       │                         │  order.status='cancelled'│
       │                         │                         │
       │<────────────────────────│                         │
```

### 4.6 예외 처리 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              예외 발생 시 흐름                            │
│                                                                          │
│  views.py ──> services.py ──> 예외 발생!                                 │
│                                   │                                      │
│                                   │  raise InsufficientStockError(...)   │
│                                   ▼                                      │
│                          ┌─────────────────┐                             │
│                          │modules/products/│                             │
│                          │ exceptions.py   │                             │
│                          │                 │                             │
│                          │ class Insuffici-│                             │
│                          │ entStockError:  │                             │
│                          │   product_id    │                             │
│                          │   requested     │                             │
│                          │   available     │                             │
│                          └────────┬────────┘                             │
│                                   │                                      │
│                                   ▼                                      │
│                          ┌─────────────────┐                             │
│                          │ shared/         │                             │
│                          │ exceptions.py   │                             │
│                          │                 │                             │
│                          │ custom_excepti- │                             │
│                          │ on_handler()    │                             │
│                          └────────┬────────┘                             │
│                                   │                                      │
│                                   ▼                                      │
│                          ┌─────────────────┐                             │
│                          │ HTTP Response   │                             │
│                          │                 │                             │
│                          │ 400 Bad Request │                             │
│                          │ {               │                             │
│                          │   "error": "...",                             │
│                          │   "code": "INSUFFICIENT_STOCK",               │
│                          │   "product_id": "xxx",                        │
│                          │   "requested": 5,                             │
│                          │   "available": 2                              │
│                          │ }               │                             │
│                          └─────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 역할 분배 (5명 팀)

| 담당자 | 모듈 | 주요 작업 |
|--------|------|-----------|
| A | users | 인증, 회원가입, 프로필 |
| B | products | 상품 CRUD, 카테고리 |
| C | products | 시맨틱 검색, pgvector, AI |
| D | orders | 장바구니, 주문, 결제 |
| E | shared + 인프라 | 공통 모듈, Docker, CI/CD |

---

## 5. API 엔드포인트

### 인증 (Auth)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/users/register/` | 회원가입 |
| POST | `/api/v1/users/login/` | 로그인 |
| POST | `/api/v1/users/token/refresh/` | 토큰 갱신 |

### 사용자 (Users)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/users/me/` | 내 정보 |
| PATCH | `/api/v1/users/me/` | 내 정보 수정 |
| GET | `/api/v1/users/` | 사용자 목록 |
| GET | `/api/v1/users/{id}/` | 사용자 상세 |

### 상품 (Products)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/products/` | 상품 목록 |
| POST | `/api/v1/products/` | 상품 생성 |
| GET | `/api/v1/products/{id}/` | 상품 상세 |
| PATCH | `/api/v1/products/{id}/` | 상품 수정 |
| DELETE | `/api/v1/products/{id}/` | 상품 삭제 |
| GET | `/api/v1/products/search/` | 상품 검색 |
| GET | `/api/v1/products/categories/` | 카테고리 목록 |

### 주문 (Orders)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/orders/cart/` | 장바구니 조회 |
| POST | `/api/v1/orders/cart/` | 장바구니 추가 |
| DELETE | `/api/v1/orders/cart/` | 장바구니 비우기 |
| PATCH | `/api/v1/orders/cart/{product_id}/` | 수량 변경 |
| DELETE | `/api/v1/orders/cart/{product_id}/` | 항목 삭제 |
| GET | `/api/v1/orders/` | 주문 목록 |
| POST | `/api/v1/orders/` | 주문 생성 |
| GET | `/api/v1/orders/{id}/` | 주문 상세 |
| DELETE | `/api/v1/orders/{id}/` | 주문 취소 |

### 카테고리 (Categories)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/categories/` | 카테고리 목록 |
| POST | `/api/v1/categories/` | 카테고리 생성 (Admin) |
| GET | `/api/v1/categories/tree/` | 카테고리 트리 |
| GET | `/api/v1/categories/{id}/` | 카테고리 상세 |
| PATCH | `/api/v1/categories/{id}/` | 카테고리 수정 (Admin) |
| DELETE | `/api/v1/categories/{id}/` | 카테고리 삭제 (Admin) |
| GET | `/api/v1/categories/{id}/subcategories/` | 하위 카테고리 |
| GET | `/api/v1/categories/{id}/breadcrumbs/` | 브레드크럼 |
| GET | `/api/v1/categories/{id}/attributes/` | 카테고리 속성 |

### 검색 (Search)
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/v1/search/` | 상품 검색 (키워드/시맨틱/하이브리드) |
| GET | `/api/v1/search/suggestions/` | 검색어 자동완성 |
| GET | `/api/v1/search/popular/` | 인기 검색어 |
| GET | `/api/v1/search/history/` | 내 검색 기록 |
| GET | `/api/v1/search/analytics/` | 검색 통계 (Admin) |

### 가격 예측 (Price Prediction)
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/predictions/` | 상품 가격 예측 조회 |
| POST | `/api/v1/predictions/create/` | 가격 예측 생성 |
| GET | `/api/v1/predictions/trend/` | 가격 트렌드 분석 |

### 헬스 체크
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/v1/health/` | 기본 헬스 체크 |
| GET | `/api/v1/health/ready/` | 준비 상태 (DB, Cache) |
| GET | `/api/v1/health/live/` | 생존 상태 |

---

## 6. 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| Framework | Django 5.0 + Django REST Framework |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Message Broker | RabbitMQ 3.12 |
| Task Queue | Celery |
| Storage | MinIO (개발) / AWS S3 (운영) |
| AI | OpenAI Embedding + Google Gemini |
| Monitoring | Prometheus + Grafana |
| Documentation | drf-spectacular (Swagger) |
| Container | Docker + Docker Compose |

---

## 7. 실행 방법

### 개발 환경 시작

```bash
# 1. 환경 변수 설정
cp .env.example .env

# 2. Docker Compose 시작
docker-compose up -d

# 3. 마이그레이션 실행
docker-compose exec backend python manage.py migrate

# 4. 슈퍼유저 생성
docker-compose exec backend python manage.py createsuperuser
```

### 서비스 URL

| 서비스 | URL | 인증 정보 |
|--------|-----|-----------|
| Django API | http://localhost:8000 | - |
| Swagger UI | http://localhost:8000/api/docs/ | - |
| ReDoc | http://localhost:8000/api/redoc/ | - |
| Admin | http://localhost:8000/admin/ | 슈퍼유저 |
| RabbitMQ | http://localhost:15672 | admin / admin123 |
| MinIO | http://localhost:9001 | minioadmin / minioadmin |
| Flower | http://localhost:5555 | - |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin / admin123 |

---

## 8. Git 브랜치 전략

```
main
└── develop
    ├── feature/users-auth         ← A
    ├── feature/products-crud      ← B
    ├── feature/products-search    ← C
    ├── feature/orders-cart        ← D
    └── feature/shared-infra       ← E
```

### 커밋 메시지 규칙

```
[module] 설명

예:
[users] Add user registration API
[products] Implement semantic search with pgvector
[orders] Fix cart total calculation
[shared] Add Redis cache service
```

---

## 9. 테스트 실행

```bash
# 전체 테스트
docker-compose exec backend pytest

# 특정 모듈 테스트
docker-compose exec backend pytest modules/users/tests/

# 커버리지 포함
docker-compose exec backend pytest --cov=modules
```

---

## 10. 모듈러 모노리스의 장점

| 기준 | 모듈러 모노리스 | 마이크로서비스 |
|------|----------------|---------------|
| 학습 비용 | 낮음 | 높음 |
| 배포 복잡도 | 낮음 | 높음 |
| 모듈 경계 | 명확 | 강제됨 |
| 트랜잭션 | 쉬움 | 어려움 (분산) |
| 5명 팀 적합도 | ⭐⭐⭐ | ⭐ |

---

## 11. 참고 자료

- [Django REST Framework](https://www.django-rest-framework.org/)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Modular Monolith Architecture](https://www.kamilgrzybek.com/design/modular-monolith-primer/)
