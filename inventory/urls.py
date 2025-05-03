# inventory/urls.py
from django.urls import path
from .views import (
    InventoryListView, LowStockListView,
    InventoryOperationView, InventoryHistoryListView
)

# Barcha endpointlar /api/inventory/ prefiksi bilan boshlanadi
urlpatterns = [
    path('', InventoryListView.as_view(), name='inventory-list'),
    path('low-stock/', LowStockListView.as_view(), name='inventory-low-stock'),
    path('history/', InventoryHistoryListView.as_view(), name='inventory-history'),
    # Amaliyotlar uchun alohida endpointlar
    path('add/', InventoryOperationView.as_view(), name='inventory-add'),
    path('remove/', InventoryOperationView.as_view(), name='inventory-remove'),
    path('transfer/', InventoryOperationView.as_view(), name='inventory-transfer'),
]