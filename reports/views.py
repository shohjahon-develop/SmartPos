# reports/views.py
from rest_framework import views, status, permissions
from rest_framework.response import Response
from django.utils.dateparse import parse_date
from django.utils import timezone
from datetime import timedelta, date, datetime, time # Ko'proq import
from decimal import Decimal
from rest_framework.exceptions import ValidationError # Faqat validatsiya uchun
import traceback

# --- Servis importlari ---
from .services import (
    get_dashboard_stats, get_sales_report_data, get_products_report_data,
    get_sellers_report_data, get_installments_report_data
)
# --- Model importlari (Validatsiya uchun) ---
from products.models import Kassa, Category
from sales.models import Sale # PaymentType uchun
from installments.models import InstallmentPlan # PlanStatus uchun
from users.models import User # seller_id validatsiyasi uchun (agar kerak bo'lsa)
# from customers.models import Customer # customer_id validatsiyasi uchun (agar kerak bo'lsa)


# --- Dashboard View (O'zgarishsiz) ---
class DashboardStatsView(views.APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        # Kassa ID sini olish (avvalgidek)
        kassa_id_str = request.query_params.get('kassa_id', None)
        final_kassa_id = None
        if kassa_id_str:
            try:
                final_kassa_id = int(kassa_id_str)
                # Kassa mavjudligini tekshirish (agar kerak bo'lsa)
                # if not Kassa.objects.filter(pk=final_kassa_id).exists():
                #     return Response({"error": "Ko'rsatilgan kassa topilmadi."}, status=status.HTTP_404_NOT_FOUND)
            except ValueError:
                return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Agar kassa ID berilmasa, birinchi aktiv kassani olish (ixtiyoriy)
            first_active_kassa = Kassa.objects.filter(is_active=True).first()
            if first_active_kassa:
                final_kassa_id = first_active_kassa.id

        # YANGI: Period turini olish
        period_type = request.query_params.get('period_type',
                                               'all').lower()  # Default 'all', kichik harflarga o'tkazish
        if period_type not in ['daily', 'monthly', 'all']:
            return Response(
                {"error": "Noto'g'ri 'period_type' qiymati. 'daily', 'monthly' yoki 'all' bo'lishi mumkin."},
                status=status.HTTP_400_BAD_REQUEST)

        try:
            # get_dashboard_stats ga period_type ni ham uzatamiz
            stats = get_dashboard_stats(kassa_id=final_kassa_id, period_type=period_type)
            if not stats:  # Agar stats bo'sh lug'at qaytarsa (masalan, faqat kassa balansi so'ralganda)
                return Response(
                    {"message": "Belgilangan davr uchun ma'lumot topilmadi yoki faqat kassa balansi hisoblandi."},
                    status=status.HTTP_200_OK)  # Yoki 404
            return Response(stats)
        except Exception as e:
            # Xatolikni loglash muhim!
            print(f"!!! ERROR in DashboardStatsView: {e}")
            import traceback
            print(traceback.format_exc())
            return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# --- BaseReportView (Endi ishlatilmaydi - O'chirish yoki Kommentga Olish) ---
# class BaseReportView(views.APIView):
#     ...


# --- Alohida Hisobot Viewlari ---

class SalesReportView(views.APIView):
    """Sotuvlar hisoboti uchun API view (Alohida)"""
    permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser

    def get(self, request):
        query_params = request.query_params
        try:
            # Majburiy sanalarni olish va validatsiya qilish
            start_date_str = query_params.get('start_date')
            end_date_str = query_params.get('end_date')
            if not start_date_str: raise ValueError("'start_date' parametri majburiy.")
            if not end_date_str: raise ValueError("'end_date' parametri majburiy.")

            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            if not start_date or not end_date: raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD).")
            if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")

            # Ixtiyoriy parametrlarni olish va validatsiya qilish
            currency = query_params.get('currency', 'UZS').upper()
            if currency not in ['UZS', 'USD']: raise ValueError("Valyuta 'UZS' yoki 'USD' bo'lishi kerak.")

            seller_id = query_params.get('seller_id')
            kassa_id = query_params.get('kassa_id')
            payment_type = query_params.get('payment_type')
            group_by = query_params.get('group_by')

            # ID larni int ga o'tkazish (agar mavjud bo'lsa)
            if seller_id: seller_id = int(seller_id)
            if kassa_id: kassa_id = int(kassa_id)

            # Payment Type va Group By validatsiyasi (agar kerak bo'lsa)
            if payment_type and payment_type not in Sale.PaymentType.values: raise ValueError("Noto'g'ri to'lov turi.")
            if group_by and group_by not in ['day', 'week', 'month']: raise ValueError("Noto'g'ri guruhlash turi.")

            # Servis funksiyasini chaqirish
            report_data = get_sales_report_data(
                start_date=start_date, end_date=end_date, currency=currency,
                seller_id=seller_id, kassa_id=kassa_id,
                payment_type=payment_type, group_by=group_by
            )
            return Response(report_data)

        except (ValueError, TypeError) as e:
             return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"!!! ERROR generating Sales Report: {e}"); traceback.print_exc()
            return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductsReportView(views.APIView):
    """Mahsulotlar hisoboti uchun API view (Alohida)"""
    permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser

    def get(self, request):
        query_params = request.query_params
        try:
            start_date_str = query_params.get('start_date')
            end_date_str = query_params.get('end_date')
            if not start_date_str: raise ValueError("'start_date' parametri majburiy.")
            if not end_date_str: raise ValueError("'end_date' parametri majburiy.")

            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            if not start_date or not end_date: raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD).")
            if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")

            currency = query_params.get('currency', 'UZS').upper()
            if currency not in ['UZS', 'USD']: raise ValueError("Valyuta 'UZS' yoki 'USD' bo'lishi kerak.")

            category_id = query_params.get('category_id')
            if category_id: category_id = int(category_id)

            report_data = get_products_report_data(
                start_date=start_date, end_date=end_date,
                currency=currency, category_id=category_id
            )
            return Response(report_data)

        except (ValueError, TypeError) as e:
             return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"!!! ERROR generating Products Report: {e}"); traceback.print_exc()
            return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SellersReportView(views.APIView):
    """Sotuvchilar hisoboti uchun API view (Alohida)"""
    permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser

    def get(self, request):
        query_params = request.query_params
        try:
            start_date_str = query_params.get('start_date')
            end_date_str = query_params.get('end_date')
            if not start_date_str: raise ValueError("'start_date' parametri majburiy.")
            if not end_date_str: raise ValueError("'end_date' parametri majburiy.")

            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            if not start_date or not end_date: raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD).")
            if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")

            currency = query_params.get('currency', 'UZS').upper()
            if currency not in ['UZS', 'USD']: raise ValueError("Valyuta 'UZS' yoki 'USD' bo'lishi kerak.")

            report_data = get_sellers_report_data(
                start_date=start_date, end_date=end_date, currency=currency
            )
            return Response(report_data)

        except (ValueError, TypeError) as e:
             return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"!!! ERROR generating Sellers Report: {e}"); traceback.print_exc()
            return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InstallmentsReportView(views.APIView):
    """Nasiyalar hisoboti uchun API view (Alohida)"""
    permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser

    def get(self, request):
        query_params = request.query_params
        try:
            # Sanalar ixtiyoriy
            start_date_str = query_params.get('start_date')
            end_date_str = query_params.get('end_date')
            start_date = parse_date(start_date_str) if start_date_str else None
            end_date = parse_date(end_date_str) if end_date_str else None
            if start_date and end_date and start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")

            customer_id = query_params.get('customer_id')
            if customer_id: customer_id = int(customer_id)

            status = query_params.get('status')
            if status and status not in InstallmentPlan.PlanStatus.values: raise ValueError("Noto'g'ri status qiymati.")

            report_data = get_installments_report_data(
                start_date=start_date, end_date=end_date,
                customer_id=customer_id, status=status
            )
            return Response(report_data)

        except (ValueError, TypeError) as e:
             return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"!!! ERROR generating Installments Report: {e}"); traceback.print_exc()
            return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)