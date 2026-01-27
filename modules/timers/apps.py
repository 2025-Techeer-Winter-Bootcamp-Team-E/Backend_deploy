"""
Timers module configuration.
"""
from django.apps import AppConfig


class TimersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'modules.timers'
    verbose_name = 'Timers'

    def ready(self):
        pass
