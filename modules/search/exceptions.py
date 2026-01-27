"""
Search module exceptions.
"""
from shared.exceptions import AppException


class SearchError(AppException):
    """Base exception for search module."""
    pass


class InvalidSearchQueryError(SearchError):
    """Raised when search query is invalid."""

    def __init__(self, message: str):
        super().__init__(message, code='INVALID_SEARCH_QUERY')


class SearchServiceError(SearchError):
    """Raised when search service fails."""

    def __init__(self, message: str, original_error=None):
        self.original_error = original_error
        super().__init__(message, code='SEARCH_SERVICE_ERROR')


class EmbeddingGenerationError(SearchError):
    """Raised when embedding generation fails."""

    def __init__(self, query: str, original_error=None):
        self.query = query
        self.original_error = original_error
        message = f"Failed to generate embedding for query: {query}"
        super().__init__(message, code='EMBEDDING_GENERATION_ERROR')
