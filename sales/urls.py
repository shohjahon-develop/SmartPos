# sales/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, SaleViewSet, PosProductListView,
    CashInView, CashOutView,
    CurrencyExchangeView  # YANGI IMPORT
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'sales', SaleViewSet, basename='sale')

urlpatterns = [
    path('', include(router.urls)),
    path('pos/products/', PosProductListView.as_view(), name='pos-products'),
    path('kassa/cash-in/', CashInView.as_view(), name='kassa-cash-in'),
    path('kassa/cash-out/', CashOutView.as_view(), name='kassa-cash-out'),

    # YANGI YO'L: Valyuta ayirboshlash uchun
    path('kassa/exchange-currency/', CurrencyExchangeView.as_view(), name='kassa-exchange-currency'),
]