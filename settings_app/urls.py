# settings_app/urls.py
from django.urls import path
from .views import StoreSettingsView, CurrencyRateView

urlpatterns = [
    # Endpointlar /api/settings/store/ va /api/settings/currency/ bo'ladi
    path('store/', StoreSettingsView.as_view(), name='settings-store'),
    path('currency/', CurrencyRateView.as_view(), name='settings-currency'),
]