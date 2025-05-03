# sales/admin.py
from django.contrib import admin
from .models import Customer, Sale, SaleItem

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'email', 'created_at')
    search_fields = ('full_name', 'phone_number', 'email')
    readonly_fields = ('created_at',)

class SaleItemInline(admin.TabularInline): # Yoki StackedInline
    model = SaleItem
    # Faqat ko'rish uchun, admin panelda o'zgartirish tavsiya etilmaydi
    readonly_fields = ('product', 'quantity', 'price_at_sale_usd', 'price_at_sale_uzs', 'quantity_returned')
    extra = 0 # Yangi qo'shish uchun bo'sh qatorlar soni
    can_delete = False # Admin panelda elementlarni o'chirishni taqiqlash
    fields = ('product', 'quantity', 'price_at_sale_uzs', 'quantity_returned') # Ko'rinadigan maydonlar

    def has_add_permission(self, request, obj=None): # Yangi qo'shishni taqiqlash
        return False

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'seller', 'kassa', 'payment_type', 'total_amount_uzs', 'status', 'created_at')
    list_filter = ('status', 'payment_type', 'kassa', 'created_at', 'seller')
    search_fields = ('id', 'customer__full_name', 'customer__phone_number', 'seller__username')
    # Sotuvni admin panelda o'zgartirish mantiqiy xatoliklarga olib kelishi mumkin
    readonly_fields = ('seller', 'customer', 'kassa', 'total_amount_usd', 'total_amount_uzs', 'amount_paid_uzs', 'created_at')
    inlines = [SaleItemInline] # Sotuv elementlarini ichida ko'rsatish
    list_select_related = ('customer', 'seller', 'kassa') # Optimallashtirish

    # Admin panelda sotuv yaratish yoki o'chirishni taqiqlash
    def has_add_permission(self, request):
        return False
    # def has_delete_permission(self, request, obj=None):
    #      return False # Agar o'chirish mumkin bo'lmasligi kerak bo'lsa