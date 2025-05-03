# subscriptions/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
# ViewSet ni users.views dan import qilamiz (yoki alohida appga ko'chirsa bo'ladi)
from users.views import SuperadminSubscriptionPlanViewSet

router = DefaultRouter()
# Endpoint /api/sa/subscriptions/ bo'ladi
router.register(r'subscriptions', SuperadminSubscriptionPlanViewSet, basename='sa-subscription')

urlpatterns = [
    path('', include(router.urls)),
]