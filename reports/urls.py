# reports/urls.py
from django.urls import path
from .views import (
    DashboardStatsView,
    SalesReportView,
    ProductsReportView,
    # SellersReportView,
    InstallmentsReportView,
    InventoryStockReportView,  # Ombor qoldiqlar hisoboti uchun view
    InventoryHistoryReportView  # Ombor tarixi hisoboti uchun view
)

# Endpointlar /api/reports/ prefiksi bilan boshlanadi
# (bu prefiks asosiy SmartPos/urls.py faylida belgilanadi)

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='report-dashboard'),
    path('sales/', SalesReportView.as_view(), name='report-sales'),
    path('products/', ProductsReportView.as_view(), name='report-products'),
    # path('sellers/', SellersReportView.as_view(), name='report-sellers'),
    path('installments/', InstallmentsReportView.as_view(), name='report-installments'),

    # Ombor hisobotlari uchun yangi yo'llar (agar avval qo'shilmagan bo'lsa)
    path('inventory/stock/', InventoryStockReportView.as_view(), name='report-inventory-stock'),
    path('inventory/history/', InventoryHistoryReportView.as_view(), name='report-inventory-history'),
]