# installments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InstallmentPlanViewSet

router = DefaultRouter()
# Endpoint: /api/installments/
router.register(r'', InstallmentPlanViewSet, basename='installment')

urlpatterns = [
    path('', include(router.urls)),
]