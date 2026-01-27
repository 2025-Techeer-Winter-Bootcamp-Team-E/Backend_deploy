"""
Pytest configuration and fixtures.
"""
import pytest
from django.conf import settings


@pytest.fixture(scope='session')
def django_db_setup():
    """Configure Django test database."""
    settings.DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def user_model():
    """Get the custom user model."""
    from modules.users.models import UserModel
    return UserModel


@pytest.fixture
def create_user(user_model):
    """Factory fixture to create users."""
    def _create_user(
        email='test@example.com',
        nickname='testuser',
        password='testpass123',
        **kwargs
    ):
        return user_model.objects.create_user(
            email=email,
            nickname=nickname,
            password=password,
            **kwargs
        )
    return _create_user


@pytest.fixture
def authenticated_client(api_client, create_user):
    """Create an authenticated API client."""
    user = create_user()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_user(user_model):
    """Create an admin user."""
    return user_model.objects.create_superuser(
        email='admin@example.com',
        nickname='admin',
        password='adminpass123',
    )


@pytest.fixture
def admin_client(api_client, admin_user):
    """Create an authenticated admin API client."""
    api_client.force_authenticate(user=admin_user)
    return api_client


# Service fixtures

@pytest.fixture
def product_service():
    """Get product service instance."""
    from modules.products.services import ProductService
    return ProductService()


@pytest.fixture
def category_service():
    """Get category service instance."""
    from modules.categories.services import CategoryService
    return CategoryService()


@pytest.fixture
def storage_service():
    """Get storage (cart) service instance."""
    from modules.orders.services import StorageService
    return StorageService()


@pytest.fixture
def purchase_service():
    """Get purchase service instance."""
    from modules.orders.services import PurchaseService
    return PurchaseService()


@pytest.fixture
def search_service():
    """Get search service instance."""
    from modules.search.services import SearchService
    return SearchService()


# Model fixtures

@pytest.fixture
def category(db):
    """Create a test category."""
    from modules.categories.models import CategoryModel
    return CategoryModel.objects.create(name='Test Category')


@pytest.fixture
def product(db, category):
    """Create a test product."""
    from modules.products.models import ProductModel
    return ProductModel.objects.create(
        danawa_product_id='TEST12345',
        name='Test Product',
        lowest_price=10000,
        brand='Test Brand',
        detail_spec={'color': 'black'},
        category=category,
    )
