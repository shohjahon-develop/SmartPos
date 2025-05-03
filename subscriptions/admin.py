# subscriptions/admin.py
from django.contrib import admin
from .models import SubscriptionPlan

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_uzs', 'product_limit', 'branch_limit', 'user_limit', 'allow_installments', 'is_active')
    list_filter = ('is_active', 'allow_installments')
    search_fields = ('name',)
    list_editable = ('is_active', 'price_uzs') # Narx va statusni o'zgartirish