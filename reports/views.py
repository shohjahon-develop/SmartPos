# reports/views.py
from rest_framework import views, status, permissions
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from rest_framework.exceptions import PermissionDenied, ValidationError

from installments.models import InstallmentPlan
# Servis importlari
from .services import (
    get_dashboard_stats, get_sales_report_data, get_products_report_data,
    get_sellers_report_data, get_installments_report_data
)
# Modellarni import qilish
from products.models import Kassa # Store kerak emas
from sales.models import Customer # Modellarni import qilish yaxshi

class DashboardStatsView(views.APIView):
    """Boshqaruv paneli uchun asosiy statistikalar"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # store tekshiruvi olib tashlandi
        # user = request.user
        # if not user.is_staff: # Yoki boshqa ruxsat tekshiruvi
        #     return Response({"error": "Ruxsat yo'q."}, status=status.HTTP_403_FORBIDDEN)

        kassa_id = request.query_params.get('kassa_id', None)
        # Agar kassa berilmasa, birinchi aktiv kassani olish
        if not kassa_id:
             first_active_kassa = Kassa.objects.filter(is_active=True).first()
             if first_active_kassa: kassa_id = first_active_kassa.id
             else: kassa_id = None # Aktiv kassa yo'q

        try:
            # get_dashboard_stats endi store_id qabul qilmaydi
            stats = get_dashboard_stats(kassa_id=kassa_id)
            return Response(stats)
        except Exception as e:
            print(f"Error in DashboardStatsView: {e}")
            return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BaseReportView(views.APIView):
    """Hisobotlar uchun umumiy logikani saqlovchi asosiy view"""
    permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser
    required_params = ['start_date', 'end_date']
    optional_params = ['currency']
    data_service = None

    # get_store_id metodi olib tashlandi

    def get(self, request):
        # store_id ni olish va params ga qo'shish qismi olib tashlandi
        params = {}

        # Sanalarni olish
        if 'start_date' in self.required_params or 'end_date' in self.required_params:
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')
            if not start_date_str and 'start_date' in self.required_params: return Response({"error": "'start_date' majburiy."}, status=status.HTTP_400_BAD_REQUEST)
            if not end_date_str and 'end_date' in self.required_params: return Response({"error": "'end_date' majburiy."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                end_date = parse_date(end_date_str) if end_date_str else timezone.now().date()
                start_date = parse_date(start_date_str) if start_date_str else end_date - timedelta(days=30)
                if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
                params['start_date'] = start_date
                params['end_date'] = end_date
            except (ValueError, TypeError) as e: return Response({"error": f"Sana parametrlarida xatolik: {e}."}, status=status.HTTP_400_BAD_REQUEST)
        else: # Sanalar majburiy emas bo'lsa
             try:
                 params['start_date'] = parse_date(request.query_params.get('start_date')) if request.query_params.get('start_date') else None
                 params['end_date'] = parse_date(request.query_params.get('end_date')) if request.query_params.get('end_date') else None
                 if params['start_date'] and params['end_date'] and params['start_date'] > params['end_date']: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
             except (ValueError, TypeError) as e: return Response({"error": f"Sana parametrlarida xatolik: {e}."}, status=status.HTTP_400_BAD_REQUEST)

        # Valyutani olish
        if 'currency' in self.optional_params or 'currency' in self.required_params:
            currency = request.query_params.get('currency', 'UZS').upper()
            if currency not in ['UZS', 'USD']: return Response({"error": "Valyuta faqat 'UZS' yoki 'USD' bo'lishi mumkin."}, status=status.HTTP_400_BAD_REQUEST)
            params['currency'] = currency

        # Qo'shimcha parametrlarni olish
        try: self.extract_extra_params(request, params)
        except (ValidationError, ValueError) as e: return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Servis funksiyasini chaqirish (store_id siz)
        if not self.data_service: return Response({"error": "Hisobot xizmati aniqlanmagan."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        try:
            report_data = self.data_service(**params)
            return Response(report_data)
        except TypeError as e:
             print(f"Report service function call error: {e}")
             print(f"Service: {self.data_service.__name__}, Params: {params}")
             return Response({"error": f"Hisobot xizmatini chaqirishda xatolik: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            print(f"Error generating report ({self.data_service.__name__}): {e}")
            return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def extract_extra_params(self, request, params):
        pass # O'zgarishsiz


# Subklasslar (SalesReportView, ProductsReportView, SellersReportView, InstallmentsReportView)
# o'zgarishsiz qoladi, chunki ular BaseReportView ga tayanadi.
# Ularning extract_extra_params metodlarida store tekshiruvi bo'lmasligi kerak.

class SalesReportView(BaseReportView):
    required_params = ['start_date', 'end_date']
    optional_params = ['currency', 'seller_id', 'kassa_id', 'payment_type', 'group_by']
    data_service = get_sales_report_data
    def extract_extra_params(self, request, params):
        params['seller_id'] = request.query_params.get('seller_id')
        params['kassa_id'] = request.query_params.get('kassa_id')
        params['payment_type'] = request.query_params.get('payment_type')
        params['group_by'] = request.query_params.get('group_by')

class ProductsReportView(BaseReportView):
    required_params = ['start_date', 'end_date']
    optional_params = ['currency', 'category_id']
    data_service = get_products_report_data
    def extract_extra_params(self, request, params):
        params['category_id'] = request.query_params.get('category_id')

class SellersReportView(BaseReportView):
    required_params = ['start_date', 'end_date']
    optional_params = ['currency']
    data_service = get_sellers_report_data
    # extract_extra_params kerak emas

class InstallmentsReportView(BaseReportView):
    required_params = []
    optional_params = ['start_date', 'end_date', 'customer_id', 'status']
    data_service = get_installments_report_data
    def extract_extra_params(self, request, params):
        params['customer_id'] = request.query_params.get('customer_id')
        params['status'] = request.query_params.get('status')
        if params['status'] and params['status'] not in InstallmentPlan.PlanStatus.values:
             raise ValueError(f"Noto'g'ri status qiymati.")