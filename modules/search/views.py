"""
Search API views.
"""
import logging
import traceback
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse # OpenApiResponse 추가

logger = logging.getLogger(__name__)

from .services import SearchService, RecentViewProductService
from .llm_service import LLMRecommendationService
from .shopping_research_service import ShoppingResearchService
from .serializers import (
    SearchQuerySerializer,
    SearchResultSerializer,
    SearchHistorySerializer,
    RecentViewProductSerializer,
    RecentViewProductCreateSerializer,
    AutocompleteResponseSerializer,
    PopularTermsResponseSerializer,
    RecentSearchSerializer,
    RecentSearchResponseSerializer,
    LLMRecommendationRequestSerializer,
    LLMRecommendationResponseSerializer,
    ShoppingResearchQuestionsRequestSerializer,
    ShoppingResearchQuestionsResponseSerializer,
    ShoppingResearchRecommendationsRequestSerializer,
    ShoppingResearchRecommendationsResponseSerializer,
)

class SearchView(APIView):
    """Main search endpoint."""
    permission_classes = [AllowAny]
    search_service = SearchService()

    @extend_schema(
        tags=['Search'],
        summary='상품 검색',
        request={
            "application/x-www-form-urlencoded": SearchQuerySerializer,
        },
        responses={200: SearchResultSerializer},
    )
    def post(self, request):
        serializer = SearchQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user_id = request.user.id if request.user.is_authenticated else None
        results = self.search_service.search_products(
            query=data['query'], search_mode=data['search_mode'], user_id=user_id
        )
        return Response(results)

class SearchHistoryView(APIView):
    """User search history."""
    permission_classes = [IsAuthenticated]
    search_service = SearchService()

    @extend_schema(
        tags=['Search'],
        summary='검색 히스토리 조회',
        parameters=[OpenApiParameter(name='limit', type=int, required=False)],
        responses={200: SearchHistorySerializer(many=True)},
    )
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        history = self.search_service.get_user_search_history(user_id=request.user.id, limit=limit)
        return Response(SearchHistorySerializer(history, many=True).data)

class RecentViewProductsView(APIView):
    """Recent view products endpoint."""
    permission_classes = [IsAuthenticated]
    recent_view_service = RecentViewProductService()

    @extend_schema(
        tags=['Search'],
        summary='최근 본 상품 목록 조회',
        parameters=[OpenApiParameter(name='limit', type=int, required=False)],
        responses={200: RecentViewProductSerializer(many=True)},
    )
    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        views = self.recent_view_service.get_user_recent_views(user_id=request.user.id, limit=limit)
        return Response(RecentViewProductSerializer(views, many=True).data)

    @extend_schema(
        tags=['Search'],
        summary='상품 조회 기록 저장',
        request=RecentViewProductCreateSerializer,
        responses={201: RecentViewProductSerializer},
    )
    def post(self, request):
        serializer = RecentViewProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        view = self.recent_view_service.record_view(
            user_id=request.user.id, danawa_product_id=serializer.validated_data['danawa_product_id']
        )
        return Response(RecentViewProductSerializer(view).data, status=status.HTTP_201_CREATED)

class RecentViewProductDeleteView(APIView):
    """Delete recent view product endpoint."""
    permission_classes = [IsAuthenticated]
    recent_view_service = RecentViewProductService()

    @extend_schema(tags=['Search'], summary='최근 본 상품 기록 삭제')
    def delete(self, request, danawa_product_id: str):
        self.recent_view_service.delete_recent_view(user_id=request.user.id, danawa_product_id=danawa_product_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
    
@extend_schema(tags=['Search'])
class AutocompleteView(APIView):
    """검색어 자동완성 API 엔드포인트"""
    permission_classes = [AllowAny]
    search_service = SearchService()

    @extend_schema(
        
        summary='검색어 자동 완성',
        parameters=[
            OpenApiParameter(name='keyword', type=str, description='사용자가 입력 중인 검색어', required=True),
        ],
        responses={
            # 기존 AutocompleteBaseResponseSerializer에서 임포트된 이름으로 수정
            200: AutocompleteResponseSerializer, 
            # OpenApiParameter 대신 OpenApiResponse를 사용해야 Swagger에 나타납니다
            500: OpenApiResponse(description='서버 내부 오류') 
        },
    )
    def get(self, request):
        keyword = request.query_params.get('keyword', '')
        try:
            suggestions = self.search_service.get_autocomplete_suggestions(keyword)
            return Response({
                "status": 200,
                "message": "자동완성 목록 조회 성공",
                "data": {"suggestions": suggestions}
            }, status=status.HTTP_200_OK)
        except Exception:
            return Response({
                "status": 500, "message": "서버 내부 오류가 발생했습니다."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@extend_schema(tags=['Search'])
class PopularSearchView(APIView):
    """인기 검색어 조회 API - 로그인 없이 누구나 조회 가능"""
    permission_classes = [AllowAny] # 인증 없이 접근 허용
    search_service = SearchService()

    @extend_schema(
        summary="인기 검색어 조회",
        responses={200: PopularTermsResponseSerializer},
        # 명시적으로 보안 설정을 비워둡니다 (Swagger에서 자물쇠 아이콘 제거)
        
    )
    def get(self, request):
        popular_terms = self.search_service.get_popular_terms()
        
        return Response({
            "status": 200,
            "message": "검색어 목록 조회 성공",
            "data": {
                "popular_terms": popular_terms
            }
        })
class RecentSearchView(APIView):
    """최근 검색어 조회 API - 검색창 드롭다운용 (최근 5개)"""
    permission_classes = [IsAuthenticated] # [cite: 9]
    search_service = SearchService()

    @extend_schema(
        tags=['Search'],
        summary='최근 검색어 조회 (5개)',
        responses={200: RecentSearchResponseSerializer}
    )
    def get(self, request):
        # PDF 명세에 따라 5개만 조회 
        history = self.search_service.get_user_search_history(
            user_id=request.user.id, 
            limit=5
        )
        
        # 데이터 형식 맞춤 [cite: 15, 18]
        serializer = RecentSearchSerializer(history, many=True)
        
        return Response({
            "status": 200,
            "message": "검색어 목록 조회 성공",
            "data": {
                "recent_terms": serializer.data
            }
        }, status=status.HTTP_200_OK)


@extend_schema(tags=['Search'])
class LLMRecommendationView(APIView):
    """
    LLM 기반 상품 추천 검색 API.

    자연어 쿼리를 분석하여 의도(Intent)를 추출하고,
    HNSW(벡터) + GIN(키워드) 하이브리드 검색으로 최적의 상품 5개를 추천합니다.
    """
    permission_classes = [IsAuthenticated]
    llm_service = LLMRecommendationService()
    search_service = SearchService()

    @extend_schema(
        summary='LLM 기반 상품 추천 검색',
        description='자연어 쿼리를 분석하여 의도를 추출하고, 하이브리드 검색으로 최적의 상품 5개를 추천합니다.',
        request=LLMRecommendationRequestSerializer,
        responses={
            200: LLMRecommendationResponseSerializer,
            401: OpenApiResponse(description='로그인이 필요합니다.'),
            500: OpenApiResponse(description='AI 분석 또는 벡터 검색 과정에서 오류가 발생했습니다.'),
        },
    )
    def post(self, request):
        # 1. 요청 검증
        serializer = LLMRecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_query = serializer.validated_data['user_query']

        try:
            # 2. LLM 추천 서비스 호출
            result = self.llm_service.get_recommendations(user_query)

            # 3. 검색 기록 저장 (search_mode='llm')
            self.search_service.record_search(
                user_id=request.user.id,
                query=user_query,
                search_mode='llm',
                danawa_product_id=''
            )

            # 4. 응답 반환
            return Response({
                "status": 200,
                "message": "추천 검색 성공",
                "data": result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": 500,
                "message": "AI 분석 또는 벡터 검색 과정에서 오류가 발생했습니다.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=['Search'])
class QuestionsView(APIView):
    """
    쇼핑 리서치 1단계 API: 맞춤형 질문 생성.

    사용자의 검색 쿼리를 분석하여 최적의 상품 추천을 위한
    맞춤형 질문 4개를 생성합니다.
    """
    permission_classes = [AllowAny]
    shopping_research_service = ShoppingResearchService()

    @extend_schema(
        summary='쇼핑 리서치 질문 생성',
        description='사용자의 검색 쿼리를 분석하여 맞춤형 질문 4개를 생성합니다.',
        request=ShoppingResearchQuestionsRequestSerializer,
        responses={
            200: ShoppingResearchQuestionsResponseSerializer,
            400: OpenApiResponse(description='유효성 검사 실패'),
            500: OpenApiResponse(description='서버 내부 오류가 발생했습니다.'),
        },
    )
    def post(self, request):
        # 1. 요청 검증
        serializer = ShoppingResearchQuestionsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_query = serializer.validated_data['user_query']

        try:
            # 2. 질문 생성
            result = self.shopping_research_service.generate_questions(user_query)

            # 3. 응답 반환
            return Response({
                "status": 200,
                "message": "질문 생성 성공",
                "data": result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "status": 500,
                "message": "서버 내부 오류가 발생했습니다.",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(tags=['Search'])
class ShoppingResearchView(APIView):
    """
    쇼핑 리서치 2단계 API: 상품 분석 및 추천.

    설문 응답을 분석하여 벡터 유사도 90% 이상의
    최적 상품 5개를 추천합니다.
    """
    permission_classes = [AllowAny]
    shopping_research_service = ShoppingResearchService()

    @extend_schema(
        summary='쇼핑 리서치 상품 추천',
        description='설문 응답을 분석하여 최적의 상품 5개를 추천합니다.',
        request=ShoppingResearchRecommendationsRequestSerializer,
        responses={
            200: ShoppingResearchRecommendationsResponseSerializer,
            400: OpenApiResponse(description='모든 질문에 대한 답변이 필요합니다.'),
            500: OpenApiResponse(description='서버 내부 오류가 발생했습니다.'),
        },
    )
    def post(self, request):
        # 1. 요청 검증
        serializer = ShoppingResearchRecommendationsRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        search_id = serializer.validated_data['search_id']
        user_query = serializer.validated_data['user_query']
        survey_contents = serializer.validated_data['survey_contents']

        try:
            # 2. 상품 추천
            result = self.shopping_research_service.get_recommendations(
                search_id=search_id,
                user_query=user_query,
                survey_contents=survey_contents
            )

            # 3. 응답 반환
            return Response({
                "status": 200,
                "message": "쇼핑 리서치 결과 분석 성공 (상위 5개 상품)",
                "data": result
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            # API 키 관련 에러는 400 Bad Request로 반환
            error_msg = str(e)
            logger.error(f"쇼핑 리서치 API 키 오류: {error_msg}")
            return Response({
                "status": 400,
                "message": error_msg,
                "error": error_msg
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"쇼핑 리서치 추천 중 오류 발생: {str(e)}")
            logger.error(f"Traceback: {error_traceback}")
            logger.error(f"Request data: search_id={search_id}, user_query={user_query}, survey_contents={survey_contents}")
            
            # OpenAI API 키 오류인 경우 특별 처리
            error_str = str(e)
            if 'API key' in error_str or 'invalid_api_key' in error_str or 'Incorrect API key' in error_str:
                return Response({
                    "status": 400,
                    "message": "OpenAI API 키가 올바르지 않습니다. 서버 관리자에게 문의하세요.",
                    "error": error_str
                }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                "status": 500,
                "message": "서버 내부 오류가 발생했습니다.",
                "error": str(e),
                "detail": error_traceback if settings.DEBUG else None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)