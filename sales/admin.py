# sales/admin.py
from django.contrib import admin
from .models import Customer, Sale, SaleItem

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'email', 'created_at')
    search_fields = ('full_name', 'phone_number', 'email')
    readonly_fields = ('created_at',)


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    readonly_fields = ('product', 'quantity',
                       'price_at_sale_currency', # Bu SaleItem dagi yakuniy sotilgan narx
                       'original_price_at_sale_usd', # SaleItem dagi asl katalog narxlari
                       'original_price_at_sale_uzs',
                       'quantity_returned')
    extra = 0
    can_delete = False
    fields = ('product', 'quantity', 'price_at_sale_currency',
              'original_price_at_sale_uzs', 'original_price_at_sale_usd',
              'quantity_returned')

    def has_add_permission(self, request, obj=None):
        return False


admin.site.register(Sale)
# @admin.register(Sale)
# class SaleAdmin(admin.ModelAdmin):
#     list_display = (
#         'id',
#         'customer',
#         'seller',
#         'kassa',
#         'payment_type',
#         'currency',  # Sotuv valyutasi
#         'original_total_amount_currency',  # Asl jami summa
#         'final_amount_currency',  # Chegirmadan keyingi yakuniy summa
#         'amount_actually_paid_at_sale',  # Haqiqatda to'langan summa
#         'status',
#         'created_at'
#     )
#     list_filter = ('status', 'payment_type', 'kassa', 'currency', 'created_at', 'seller')
#     search_fields = ('id', 'customer__full_name', 'customer__phone_number', 'seller__username')
#
#     readonly_fields = (
#         'seller',
#         'customer',
#         'kassa',
#         'currency',
#         'original_total_amount_currency',  # Odatda hisoblanadi
#         'final_amount_currency',  # Odatda hisoblanadi yoki kiritiladi
#         'amount_actually_paid_at_sale',  # Odatda hisoblanadi
#         'created_at',
#         # Agar discount_amount_currency property bo'lsa, uni ham qo'shish mumkin
#         # 'discount_amount_currency'
#     )
#     inlines = [SaleItemInline]
#     list_select_related = ('customer', 'seller', 'kassa')
#
#     def has_add_permission(self, request):
#         return False  # Odatda API orqali yaratiladi