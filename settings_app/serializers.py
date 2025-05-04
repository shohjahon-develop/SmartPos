# settings_app/serializers.py
from rest_framework import serializers
from .models import StoreSettings, CurrencyRate

class StoreSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreSettings
        # Faqat o'zgartirish mumkin bo'lgan maydonlar
        fields = ['name', 'address', 'phone', 'email']

class CurrencyRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyRate
        fields = ['usd_to_uzs_rate', 'last_updated']
        # ---- Tekshiring ----
        read_only_fields = ('last_updated',) # KORTEJ YOKI LIST (vergul muhim)
        # Yoki: read_only_fields = ['last_updated']