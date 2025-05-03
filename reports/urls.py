# reports/urls.py
from django.urls import path
from .views import (
    DashboardStatsView, SalesReportView, ProductsReportView,
    SellersReportView, InstallmentsReportView
)

# Endpointlar /api/reports/ prefiksi bilan boshlanadi
urlpatterns = [
    path('dashboard/', DashboardStatsView.as_view(), name='report-dashboard'),
    path('sales/', SalesReportView.as_view(), name='report-sales'),
    path('products/', ProductsReportView.as_view(), name='report-products'),
    path('sellers/', SellersReportView.as_view(), name='report-sellers'),
    path('installments/', InstallmentsReportView.as_view(), name='report-installments'),
]