# 쇼핑 리서치 기능 문제 해결 가이드

## 개요
쇼핑 리서치 기능(질문 생성 및 응답)이 작동하지 않았던 원인과 해결 과정을 정리한 문서입니다.

---

## 주요 문제 및 해결

### 1. OpenAI API 키 오류

#### 문제 증상
```
ERROR: OpenAI API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 설정해주세요.
ERROR: OpenAI embedding 생성 실패
```

#### 원인
1. **`.env` 파일에 API 키가 설정되지 않음**
   - `.env` 파일에 `OPENAI_API_KEY=your-openai-api-key` (예제 값)이 그대로 남아있음
   - 실제 API 키가 파일 하단에 주석 형태로만 존재

2. **Docker 컨테이너가 환경 변수를 재로드하지 않음**
   - `.env` 파일을 수정했지만 Docker 컨테이너가 재시작되지 않아 새로운 환경 변수를 읽지 못함

3. **과도한 API 키 검증 로직**
   - `Backend/shared/ai_clients.py`에 추가된 검증 로직이 실제로는 설정된 키를 못 읽고 있을 수 있음

#### 해결 방법
1. **`.env` 파일 수정**
   ```env
   # ❌ 잘못된 예시
   OPENAI_API_KEY=your-openai-api-key
   
   # ✅ 올바른 예시
   OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

2. **Docker 컨테이너 재시작**
   ```bash
   cd Backend
   docker compose restart backend
   # 또는 완전 재시작
   docker compose down
   docker compose up -d backend
   ```

3. **API 키 검증 로직 제거 (원래대로 복구)**
   - `Backend/shared/ai_clients.py`의 `create_embedding` 메서드에서 과도한 검증 로직 제거
   - 원래는 단순히 API를 호출하고, 에러가 발생하면 OpenAI SDK가 자체적으로 에러를 반환

---

### 2. Gemini API 키 오류

#### 문제 증상
```
WARNING: Survey analysis failed: 400 API key not valid. Please pass a valid API key. [reason: "API_KEY_INVALID"]
```

#### 원인
- `.env` 파일에 `GEMINI_API_KEY=your-gemini-api-key` (예제 값)이 그대로 남아있음
- 실제 Gemini API 키가 파일 하단에 주석 형태로만 존재

#### 해결 방법
1. **`.env` 파일 수정**
   ```env
   # ❌ 잘못된 예시
   GEMINI_API_KEY=your-gemini-api-key
   
   # ✅ 올바른 예시
   GEMINI_API_KEY=AIzaSyC81I_z9fdoVqg2IhFTkhuNjivXZhelFrI
   ```

2. **Docker 컨테이너 재시작** (위와 동일)

---

### 3. 프론트엔드 필드명 불일치

#### 문제 증상
- 쇼핑 리서치 결과 페이지에서 `product: Array(0)` (빈 배열) 반환
- 프론트엔드에서 `data?.products`로 접근 시 `undefined`

#### 원인
- **백엔드**: `"product"` (단수) 필드로 반환
- **프론트엔드**: `products` (복수) 필드를 기대
- 타입 정의와 실제 응답 구조가 불일치

#### 해결 방법
- 백엔드와 프론트엔드를 모두 `product` (단수)로 통일
- `Backend/modules/search/shopping_research_service.py`: `"product": products`
- `Backend/modules/search/serializers.py`: `product = ProductRecommendationSerializer(...)`
- `Frontend/src/types/searchType.ts`: `product: ShoppingResearchResultEntity[]`
- `Frontend/src/pages/ShoppingResearchResultPage.tsx`: `data?.product`

---

### 4. 검색 버튼 클릭 불가

#### 문제 증상
- 메인 페이지의 돋보기(검색) 버튼이 클릭되지 않음
- 버튼을 클릭해도 아무 반응 없음

#### 원인
1. **z-index 문제**: 다른 요소가 버튼을 가리고 있음
2. **pointer-events 문제**: Search 아이콘이 클릭 이벤트를 가로챔
3. **이벤트 핸들러 문제**: `preventDefault`, `stopPropagation` 누락

#### 해결 방법
```tsx
<button
  onClick={handleSearch}
  disabled={!query.trim()}
  className="relative z-10 flex h-12 w-12 items-center justify-center self-end rounded-full bg-black text-white transition-opacity hover:opacity-80 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:opacity-50"
  type="button"
  aria-label="검색"
>
  <Search className="h-5 w-5 pointer-events-none" />
</button>
```

**주요 수정사항:**
- `relative z-10`: 버튼이 다른 요소 위에 표시되도록
- `pointer-events-none` (아이콘): 아이콘이 클릭을 방해하지 않도록
- `type="button"`: form 내부에서 submit 방지
- 이벤트 핸들러에 `preventDefault`, `stopPropagation` 추가

---

### 5. React Key 중복 경고

#### 문제 증상
```
Encountered two children with the same key, `5`. Keys should be unique...
```

#### 원인
- `ComparisonTable` 컴포넌트에서 `product.product_code`를 key로 사용
- 같은 `product_code`를 가진 상품이 여러 개일 수 있음 (같은 행에서 여러 번 렌더링)

#### 해결 방법
```tsx
// ❌ 잘못된 예시
{products.map((product) => (
  <td key={product.product_code}>...</td>
))}

// ✅ 올바른 예시
{products.map((product, index) => (
  <td key={`price-${product.product_code}-${index}`}>...</td>
))}
```

각 테이블 행마다 고유한 key 생성:
- `key={`product-${product.product_code}-${index}`}` (헤더)
- `key={`price-${product.product_code}-${index}`}` (가격 행)
- `key={`performance-${product.product_code}-${index}`}` (성능 행)
- `key={`spec-${product.product_code}-${index}-${specKey}`}` (스펙 행)

---

### 6. QuestionFlow undefined 에러

#### 문제 증상
```
Uncaught TypeError: Cannot read properties of undefined (reading 'question')
at QuestionFlow (QuestionFlow.tsx:44:34)
```

#### 원인
- `questions` 배열이 비어있거나 `currentQuestionIndex`가 범위를 벗어남
- `currentQuestion`이 `undefined`인 상태에서 `currentQuestion.question` 접근

#### 해결 방법
```tsx
// 안전성 검사 추가
if (!questions || questions.length === 0) {
  return <div>질문이 없습니다.</div>;
}

const currentQuestion = questions[currentQuestionIndex];

if (!currentQuestion) {
  return <div>질문을 찾을 수 없습니다.</div>;
}

// 이후 currentQuestion 사용
```

---

## 문제 해결 체크리스트

### 환경 설정
- [ ] `.env` 파일에 실제 OpenAI API 키 설정 (예제 값 아님)
- [ ] `.env` 파일에 실제 Gemini API 키 설정 (예제 값 아님)
- [ ] Docker 컨테이너 재시작 완료
- [ ] 환경 변수가 컨테이너에 로드되었는지 확인: `docker compose exec backend env | grep OPENAI_API_KEY`

### 백엔드
- [ ] `Backend/shared/ai_clients.py`의 과도한 API 키 검증 로직 제거
- [ ] `Backend/modules/search/shopping_research_service.py`에서 `"product"` 필드로 반환
- [ ] `Backend/modules/search/serializers.py`에서 `product` 필드 사용
- [ ] 백엔드 로그에서 API 키 오류가 없는지 확인

### 프론트엔드
- [ ] `Frontend/src/types/searchType.ts`에서 `product` 필드 사용 (복수 아님)
- [ ] `Frontend/src/pages/ShoppingResearchResultPage.tsx`에서 `data?.product` 접근
- [ ] `Frontend/src/components/mainPage/MainSearchBar.tsx`의 검색 버튼이 클릭 가능한지 확인
- [ ] `Frontend/src/components/shoppingResearchResult/ComparisonTable.tsx`의 key가 고유한지 확인
- [ ] `Frontend/src/components/shoppingResearch/QuestionFlow.tsx`에 안전성 검사 추가

---

## 테스트 방법

### 1. 질문 생성 테스트
1. 메인 페이지에서 "노트북 추천해" 입력
2. 돋보기 버튼 클릭
3. 브라우저 콘솔에서 다음 로그 확인:
   - `🔵 MainSearchBar - 검색 실행: 노트북 추천해`
   - `🔵 getAPIResponseData - raw result: {...}`
   - `🟢 getAPIResponseData - extracted data: {questions: [...], search_id: "..."}`
   - `🟢 MainSearchBar - 검색 성공: {...}`
4. 쇼핑 리서치 질문 페이지로 이동하는지 확인

### 2. 응답 생성 테스트
1. 질문에 답변 입력
2. 모든 질문 완료 후 결과 페이지로 이동
3. 브라우저 콘솔에서 다음 로그 확인:
   - `🔵 ShoppingResearchResultPage - data: {...}`
   - `🔵 ShoppingResearchResultPage - product: Array(5)` (빈 배열 아님)
4. 추천 상품이 표시되는지 확인

---

## 참고 사항

### API 키 발급 방법
- **OpenAI API 키**: https://platform.openai.com/account/api-keys
- **Gemini API 키**: https://makersuite.google.com/app/apikey

### 로그 확인 방법
```bash
# Docker 사용 시
docker compose logs -f backend | grep "shopping_research\|OpenAI\|Gemini"

# 또는 특정 에러만 확인
docker compose logs backend | grep "ERROR\|WARNING"
```

### 환경 변수 확인
```bash
# 컨테이너 내부에서 확인
docker compose exec backend env | grep OPENAI_API_KEY
docker compose exec backend env | grep GEMINI_API_KEY

# Django shell에서 확인
docker compose exec backend python manage.py shell
>>> from django.conf import settings
>>> print(settings.OPENAI_API_KEY[:20] + "...")  # 처음 20자만 출력
```

---

## 결론

쇼핑 리서치 기능이 작동하지 않았던 주요 원인은:

1. **환경 변수 설정 문제** (가장 중요)
   - `.env` 파일에 실제 API 키가 설정되지 않음
   - Docker 컨테이너가 환경 변수를 재로드하지 않음

2. **과도한 검증 로직**
   - API 키 검증 로직이 실제로는 설정된 키를 못 읽고 있었음
   - 원래대로 단순하게 API를 호출하고 에러를 그대로 전달하는 방식이 더 나음

3. **프론트엔드-백엔드 필드명 불일치**
   - `products` vs `product` 불일치로 인한 데이터 접근 실패

4. **UI/UX 문제**
   - 검색 버튼 클릭 불가
   - React key 중복
   - undefined 에러

이러한 문제들을 해결한 후 쇼핑 리서치 기능이 정상적으로 작동하게 되었습니다.
