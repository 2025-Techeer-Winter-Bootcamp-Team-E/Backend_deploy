"""
Search module configuration.
"""
from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.search'
    verbose_name = 'Search'

    def ready(self):
        pass
