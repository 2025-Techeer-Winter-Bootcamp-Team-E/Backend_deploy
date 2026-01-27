"""
Categories module exceptions.
"""
from shared.exceptions import AppException


class CategoryError(AppException):
    """Base exception for categories module."""
    pass


class CategoryNotFoundError(CategoryError):
    """Raised when category is not found."""

    def __init__(self, category_id=None, slug=None):
        self.category_id = category_id
        self.slug = slug
        if slug:
            message = f"Category not found: {slug}"
        else:
            message = f"Category not found: {category_id}"
        super().__init__(message, code='CATEGORY_NOT_FOUND')


class CategoryAlreadyExistsError(CategoryError):
    """Raised when category already exists."""

    def __init__(self, name: str):
        self.name = name
        message = f"Category already exists: {name}"
        super().__init__(message, code='CATEGORY_ALREADY_EXISTS')


class InvalidCategoryHierarchyError(CategoryError):
    """Raised when category hierarchy is invalid."""

    def __init__(self, message: str):
        super().__init__(message, code='INVALID_CATEGORY_HIERARCHY')
