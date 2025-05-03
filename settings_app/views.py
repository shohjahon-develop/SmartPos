# settings_app/views.py
from rest_framework import views, status, permissions
from rest_framework.response import Response
from .models import StoreSettings, CurrencyRate
from .serializers import StoreSettingsSerializer, CurrencyRateSerializer
# from users.permissions import IsAdminRole # Agar maxsus permission yaratgan bo'lsak
from rest_framework.permissions import IsAdminUser # Django adminlari uchun

class StoreSettingsView(views.APIView):
    """Do'konning asosiy sozlamalarini ko'rish va tahrirlash"""
    permission_classes = [IsAdminUser] # Faqat adminlar o'zgartira oladi

    def get(self, request, *args, **kwargs):
        """Joriy do'kon sozlamalarini olish"""
        settings_instance = StoreSettings.load()
        serializer = StoreSettingsSerializer(settings_instance)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        """Do'kon sozlamalarini yangilash (qisman yangilash ham mumkin)"""
        settings_instance = StoreSettings.load()
        # partial=True PUT so'rovida ham faqat kelgan maydonlarni yangilashga imkon beradi
        serializer = StoreSettingsSerializer(settings_instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CurrencyRateView(views.APIView):
    """Valyuta kursini ko'rish va tahrirlash"""
    permission_classes = [IsAdminUser] # Faqat adminlar

    def get(self, request, *args, **kwargs):
        """Joriy valyuta kursini olish"""
        rate_instance = CurrencyRate.load()
        serializer = CurrencyRateSerializer(rate_instance)
        return Response(serializer.data)

    def put(self, request, *args, **kwargs):
        """Valyuta kursini yangilash"""
        rate_instance = CurrencyRate.load()
        # Bu yerda ham partial=True ishlatamiz, faqat 'usd_to_uzs_rate' kelishi kutiladi
        serializer = CurrencyRateSerializer(rate_instance, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Muvaffaqiyatli yangilangan kursni qaytarish
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)