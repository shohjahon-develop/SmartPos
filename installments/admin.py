# installments/admin.py
from django.contrib import admin
from .models import InstallmentPlan, InstallmentPayment

class InstallmentPaymentInline(admin.TabularInline):
    model = InstallmentPayment
    extra = 0
    readonly_fields = ('payment_date', 'amount', 'payment_method', 'received_by')
    can_delete = False
    ordering = ('-payment_date',)

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'sale_id', 'customer', 'total_due', 'amount_paid', 'remaining_amount', 'next_payment_date', 'status', 'created_at')
    list_filter = ('status', 'next_payment_date', 'customer', 'sale__kassa')
    search_fields = ('id', 'sale__id', 'customer__full_name', 'customer__phone_number')
    readonly_fields = ('sale', 'customer', 'total_due', 'amount_paid', 'remaining_amount', 'status', 'created_at', 'return_adjustment')
    inlines = [InstallmentPaymentInline]
    list_select_related = ('customer', 'sale__kassa')

    # Admin panelda yangi plan yaratish/o'chirishni taqiqlash
    def has_add_permission(self, request):
        return False
    # def has_delete_permission(self, request, obj=None):
    #     return False # Odatda o'chirilmaydi

@admin.register(InstallmentPayment)
class InstallmentPaymentAdmin(admin.ModelAdmin):
    list_display = ('plan', 'amount', 'payment_date', 'payment_method', 'received_by')
    list_filter = ('payment_method', 'payment_date', 'received_by')
    search_fields = ('plan__id', 'plan__customer__full_name', 'received_by__username')
    readonly_fields = ('plan', 'amount', 'payment_date', 'payment_method', 'received_by') # O'zgartirib bo'lmaydi
    list_select_related = ('plan__customer', 'received_by')

    def has_add_permission(self, request):
        return False # To'lovlar faqat API orqali qo'shiladi
    def has_change_permission(self, request, obj=None):
        return False # O'zgartirib bo'lmaydi
    # def has_delete_permission(self, request, obj=None):
    #     return False # O'chirib bo'lmaydi