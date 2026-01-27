"""
Categories API views.
"""
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .services import CategoryService
from .serializers import (
    CategorySerializer,
    CategoryCreateSerializer,
    CategoryUpdateSerializer,
    CategoryTreeSerializer,
    CategoryBreadcrumbSerializer,
)
from .exceptions import CategoryNotFoundError


class CategoryListCreateView(APIView):
    """List and create categories."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category_service = CategoryService()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        tags=['Categories'],
        summary='List categories',
        parameters=[
            OpenApiParameter(
                name='root_only',
                type=bool,
                required=False,
                description='Return only root categories'
            ),
        ],
        responses={200: CategorySerializer(many=True)},
    )
    def get(self, request):
        """Get all categories."""
        root_only = request.query_params.get('root_only', '').lower() == 'true'

        if root_only:
            categories = self.category_service.get_root_categories()
        else:
            categories = self.category_service.get_all_categories()

        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['Categories'],
        summary='Create category',
        request=CategoryCreateSerializer,
        responses={201: CategorySerializer},
    )
    def post(self, request):
        """Create a new category."""
        serializer = CategoryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category = self.category_service.create_category(**serializer.validated_data)

        result_serializer = CategorySerializer(category)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    """Category detail operations."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category_service = CategoryService()

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        tags=['Categories'],
        summary='Get category',
        responses={200: CategorySerializer},
    )
    def get(self, request, category_id):
        """Get category by ID."""
        category = self.category_service.get_category_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id=category_id)

        serializer = CategorySerializer(category)
        return Response(serializer.data)

    @extend_schema(
        tags=['Categories'],
        summary='Update category',
        request=CategoryUpdateSerializer,
        responses={200: CategorySerializer},
    )
    def patch(self, request, category_id):
        """Update a category."""
        serializer = CategoryUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category = self.category_service.update_category(
            category_id=category_id,
            **serializer.validated_data
        )

        result_serializer = CategorySerializer(category)
        return Response(result_serializer.data)

    @extend_schema(
        tags=['Categories'],
        summary='Delete category',
    )
    def delete(self, request, category_id):
        """Delete a category (soft delete)."""
        self.category_service.delete_category(category_id=category_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryTreeView(APIView):
    """Get category tree structure."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category_service = CategoryService()

    @extend_schema(
        tags=['Categories'],
        summary='Get category tree',
        responses={200: CategoryTreeSerializer(many=True)},
    )
    def get(self, request):
        """Get full category tree."""
        tree = self.category_service.get_category_tree()
        return Response(tree)


class CategorySubcategoriesView(APIView):
    """Get subcategories of a category."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category_service = CategoryService()

    @extend_schema(
        tags=['Categories'],
        summary='Get subcategories',
        responses={200: CategorySerializer(many=True)},
    )
    def get(self, request, category_id):
        """Get direct children of a category."""
        subcategories = self.category_service.get_subcategories(category_id)
        serializer = CategorySerializer(subcategories, many=True)
        return Response(serializer.data)


class ProductFilterCategoriesView(APIView):
    """상품 필터링용 카테고리 트리 조회."""

    permission_classes = [AllowAny]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.category_service = CategoryService()

    @extend_schema(
        tags=['Categories'],
        summary='상품 필터용 카테고리 목록',
        description='상품 필터링 UI에서 사용할 대분류/소분류 카테고리 트리를 반환합니다.',
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'status': {'type': 'integer', 'example': 200},
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'children': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'id': {'type': 'integer'},
                                            'name': {'type': 'string'},
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
    )
    def get(self, request):
        """상품 필터용 카테고리 트리 반환."""
        categories = self.category_service.get_product_filter_categories()
        return Response({
            'status': 200,
            'data': categories
        })
