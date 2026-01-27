"""
Timers URL configuration.
"""
from django.urls import path

from .views import TimerListCreateView, TimerDetailView, TimerByProductView

app_name = 'timers'

urlpatterns = [
    path('', TimerListCreateView.as_view(), name='timer-list-create'),
    path('product/<str:product_code>/', TimerByProductView.as_view(), name='timer-by-product'),
    path('<int:timer_id>/', TimerDetailView.as_view(), name='timer-detail'),
]
