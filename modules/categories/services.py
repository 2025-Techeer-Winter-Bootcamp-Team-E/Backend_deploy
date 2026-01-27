"""
Categories business logic services.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from django.db import transaction

from .models import CategoryModel
from .exceptions import (
    CategoryNotFoundError,
    CategoryAlreadyExistsError,
    InvalidCategoryHierarchyError,
)

logger = logging.getLogger(__name__)


class CategoryService:
    """Service for category operations."""

    def get_category_by_id(self, category_id: int) -> Optional[CategoryModel]:
        """Get category by ID."""
        try:
            return CategoryModel.objects.get(id=category_id, deleted_at__isnull=True)
        except CategoryModel.DoesNotExist:
            return None

    def get_all_categories(self) -> List[CategoryModel]:
        """Get all active categories."""
        return list(
            CategoryModel.objects.filter(deleted_at__isnull=True)
            .order_by('name')
        )

    def get_root_categories(self) -> List[CategoryModel]:
        """Get top-level categories (no parent)."""
        return list(
            CategoryModel.objects.filter(
                parent__isnull=True,
                deleted_at__isnull=True
            ).order_by('name')
        )

    def get_subcategories(self, parent_id: int) -> List[CategoryModel]:
        """Get direct children of a category."""
        return list(
            CategoryModel.objects.filter(
                parent_id=parent_id,
                deleted_at__isnull=True
            ).order_by('name')
        )

    def get_category_tree(self) -> List[Dict[str, Any]]:
        """Get full category tree structure."""
        root_categories = self.get_root_categories()
        return [self._build_tree_node(cat) for cat in root_categories]

    @transaction.atomic
    def create_category(
        self,
        name: str,
        parent_id: Optional[int] = None,
    ) -> CategoryModel:
        """Create a new category."""
        parent = None
        if parent_id:
            parent = self.get_category_by_id(parent_id)
            if not parent:
                raise CategoryNotFoundError(category_id=parent_id)

        existing = CategoryModel.objects.filter(
            name__iexact=name,
            parent=parent,
            deleted_at__isnull=True
        ).exists()
        if existing:
            raise CategoryAlreadyExistsError(name=name)

        category = CategoryModel.objects.create(
            name=name,
            parent=parent,
        )

        logger.info(f"Created category: {category.name} ({category.id})")
        return category

    @transaction.atomic
    def update_category(
        self,
        category_id: int,
        name: str = None,
        parent_id: int = None,
    ) -> CategoryModel:
        """Update a category."""
        category = self.get_category_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id=category_id)

        if name is not None:
            category.name = name

        if parent_id is not None:
            if parent_id == category_id:
                raise InvalidCategoryHierarchyError("Category cannot be its own parent")
            if parent_id == 0:
                category.parent = None
            else:
                new_parent = self.get_category_by_id(parent_id)
                if not new_parent:
                    raise CategoryNotFoundError(category_id=parent_id)
                category.parent = new_parent

        category.save()
        logger.info(f"Updated category: {category.name} ({category.id})")
        return category

    @transaction.atomic
    def delete_category(self, category_id: int) -> bool:
        """Soft delete a category."""
        category = self.get_category_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id=category_id)

        category.deleted_at = datetime.now()
        category.save()
        logger.info(f"Deleted category: {category_id}")
        return True

    def _build_tree_node(self, category: CategoryModel) -> Dict[str, Any]:
        """Build a tree node for category."""
        children = CategoryModel.objects.filter(
            parent=category,
            deleted_at__isnull=True
        ).order_by('name')

        return {
            'id': category.id,
            'name': category.name,
            'level': category.level,
            'children': [self._build_tree_node(child) for child in children]
        }

    def get_product_filter_categories(self) -> List[Dict[str, Any]]:
        """
        상품 필터링용 카테고리 트리 반환.

        구조:
        - 노트북: LG그램, 삼성 갤럭시북, 게이밍 노트북, Apple 맥북, 울트라북, 일반 노트북
        - 데스크탑: 브랜드PC, 미니PC, 게이밍PC, 올인원PC, 조립PC
        - PC부품: CPU, 그래픽카드, SSD, RAM, 메인보드
        - 모니터: 4K 모니터, 게이밍 모니터, 일반 모니터
        - 주변기기: 키보드, 마우스
        """
        # 대분류별 허용할 소분류 카테고리 이름 목록
        filter_structure = {
            '노트북': ['LG 그램', '삼성 갤럭시북', '게이밍 노트북', 'Apple 맥북', '울트라북', '일반 노트북'],
            '데스크탑': ['브랜드PC', '미니PC', '게이밍PC', '올인원PC', '조립PC'],
            'PC부품': ['CPU', '그래픽카드', 'SSD', 'RAM', '메인보드'],
            '모니터': ['4K 모니터', '게이밍 모니터', '일반 모니터'],
            '주변기기': ['키보드', '마우스'],
        }

        result = []
        for main_name, sub_names in filter_structure.items():
            category = CategoryModel.objects.filter(
                name__icontains=main_name,
                deleted_at__isnull=True
            ).order_by('level').first()

            if category:
                result.append(self._build_filter_tree_node(category, sub_names))

        return result

    def _build_filter_tree_node(self, category: CategoryModel, allowed_children: List[str] = None) -> Dict[str, Any]:
        """필터용 카테고리 트리 노드 구성 (지정된 하위 카테고리만 포함)."""
        children = CategoryModel.objects.filter(
            parent=category,
            deleted_at__isnull=True
        ).order_by('name')

        # 허용된 카테고리만 필터링
        if allowed_children:
            filtered_children = [
                {'id': child.id, 'name': child.name}
                for child in children
                if child.name in allowed_children
            ]
            # 지정된 순서대로 정렬
            order_map = {name: idx for idx, name in enumerate(allowed_children)}
            filtered_children.sort(key=lambda x: order_map.get(x['name'], 999))
        else:
            filtered_children = [
                {'id': child.id, 'name': child.name}
                for child in children
            ]

        return {
            'id': category.id,
            'name': category.name,
            'children': filtered_children
        }
