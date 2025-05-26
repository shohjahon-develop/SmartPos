# reports/urls.py
from django.urls import path
from .views import (
    DashboardStatsView,
    SalesReportView,
    ProductsReportView,
    # SellersReportView, # Kommentariyada qoladi
    InstallmentsReportView,
    InventoryStockReportView,
    InventoryHistoryReportView,
    SalesChartView # YANGI VIEWNI IMPORT QILISH
)

urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='report-dashboard'),
    path('sales/', SalesReportView.as_view(), name='report-sales'),
    path('products/', ProductsReportView.as_view(), name='report-products'),
    # path('sellers/', SellersReportView.as_view(), name='report-sellers'),
    path('installments/', InstallmentsReportView.as_view(), name='report-installments'),
    path('inventory/stock/', InventoryStockReportView.as_view(), name='report-inventory-stock'),
    path('inventory/history/', InventoryHistoryReportView.as_view(), name='report-inventory-history'),

    # YANGI YO'L: Sotuvlar grafigi uchun
    path('sales-chart/', SalesChartView.as_view(), name='report-sales-chart'),
]