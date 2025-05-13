# # reports/views.py
# from rest_framework import views, status, permissions
# from rest_framework.response import Response
# from django.utils.dateparse import parse_date
# from django.utils import timezone
# from datetime import timedelta, date, datetime, time # Ko'proq import
# from decimal import Decimal
# from rest_framework.exceptions import ValidationError # Faqat validatsiya uchun
# import traceback
#
# # --- Servis importlari ---
# from .services import (
#     get_dashboard_stats, get_sales_report_data, get_products_report_data,
#     get_sellers_report_data, get_installments_report_data
# )
# # --- Model importlari (Validatsiya uchun) ---
# from products.models import Kassa, Category
# from sales.models import Sale # PaymentType uchun
# from installments.models import InstallmentPlan # PlanStatus uchun
# from users.models import User # seller_id validatsiyasi uchun (agar kerak bo'lsa)
# # from customers.models import Customer # customer_id validatsiyasi uchun (agar kerak bo'lsa)
#
#
# # --- Dashboard View (O'zgarishsiz) ---
# class DashboardStatsView(views.APIView):
#     permission_classes = [permissions.IsAdminUser]
#
#     def get(self, request):
#         # Kassa ID sini olish (avvalgidek)
#         kassa_id_str = request.query_params.get('kassa_id', None)
#         final_kassa_id = None
#         if kassa_id_str:
#             try:
#                 final_kassa_id = int(kassa_id_str)
#                 # Kassa mavjudligini tekshirish (agar kerak bo'lsa)
#                 # if not Kassa.objects.filter(pk=final_kassa_id).exists():
#                 #     return Response({"error": "Ko'rsatilgan kassa topilmadi."}, status=status.HTTP_404_NOT_FOUND)
#             except ValueError:
#                 return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)
#         else:
#             # Agar kassa ID berilmasa, birinchi aktiv kassani olish (ixtiyoriy)
#             first_active_kassa = Kassa.objects.filter(is_active=True).first()
#             if first_active_kassa:
#                 final_kassa_id = first_active_kassa.id
#
#         # YANGI: Period turini olish
#         period_type = request.query_params.get('period_type',
#                                                'all').lower()  # Default 'all', kichik harflarga o'tkazish
#         if period_type not in ['daily', 'monthly', 'all']:
#             return Response(
#                 {"error": "Noto'g'ri 'period_type' qiymati. 'daily', 'monthly' yoki 'all' bo'lishi mumkin."},
#                 status=status.HTTP_400_BAD_REQUEST)
#
#         try:
#             # get_dashboard_stats ga period_type ni ham uzatamiz
#             stats = get_dashboard_stats(kassa_id=final_kassa_id, period_type=period_type)
#             if not stats:  # Agar stats bo'sh lug'at qaytarsa (masalan, faqat kassa balansi so'ralganda)
#                 return Response(
#                     {"message": "Belgilangan davr uchun ma'lumot topilmadi yoki faqat kassa balansi hisoblandi."},
#                     status=status.HTTP_200_OK)  # Yoki 404
#             return Response(stats)
#         except Exception as e:
#             # Xatolikni loglash muhim!
#             print(f"!!! ERROR in DashboardStatsView: {e}")
#             import traceback
#             print(traceback.format_exc())
#             return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."},
#                             status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#
# # --- BaseReportView (Endi ishlatilmaydi - O'chirish yoki Kommentga Olish) ---
# # class BaseReportView(views.APIView):
# #     ...
#
#
# # --- Alohida Hisobot Viewlari ---
#
# class SalesReportView(views.APIView):
#     """Sotuvlar hisoboti uchun API view (Alohida)"""
#     permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser
#
#     def get(self, request):
#         query_params = request.query_params
#         try:
#             # Majburiy sanalarni olish va validatsiya qilish
#             start_date_str = query_params.get('start_date')
#             end_date_str = query_params.get('end_date')
#             if not start_date_str: raise ValueError("'start_date' parametri majburiy.")
#             if not end_date_str: raise ValueError("'end_date' parametri majburiy.")
#
#             start_date = parse_date(start_date_str)
#             end_date = parse_date(end_date_str)
#             if not start_date or not end_date: raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD).")
#             if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
#
#             # Ixtiyoriy parametrlarni olish va validatsiya qilish
#             currency = query_params.get('currency', 'UZS').upper()
#             if currency not in ['UZS', 'USD']: raise ValueError("Valyuta 'UZS' yoki 'USD' bo'lishi kerak.")
#
#             seller_id = query_params.get('seller_id')
#             kassa_id = query_params.get('kassa_id')
#             payment_type = query_params.get('payment_type')
#             group_by = query_params.get('group_by')
#
#             # ID larni int ga o'tkazish (agar mavjud bo'lsa)
#             if seller_id: seller_id = int(seller_id)
#             if kassa_id: kassa_id = int(kassa_id)
#
#             # Payment Type va Group By validatsiyasi (agar kerak bo'lsa)
#             if payment_type and payment_type not in Sale.PaymentType.values: raise ValueError("Noto'g'ri to'lov turi.")
#             if group_by and group_by not in ['day', 'week', 'month']: raise ValueError("Noto'g'ri guruhlash turi.")
#
#             # Servis funksiyasini chaqirish
#             report_data = get_sales_report_data(
#                 start_date=start_date, end_date=end_date, currency=currency,
#                 seller_id=seller_id, kassa_id=kassa_id,
#                 payment_type=payment_type, group_by=group_by
#             )
#             return Response(report_data)
#
#         except (ValueError, TypeError) as e:
#              return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             print(f"!!! ERROR generating Sales Report: {e}"); traceback.print_exc()
#             return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#
# class ProductsReportView(views.APIView):
#     """Mahsulotlar hisoboti uchun API view (Alohida)"""
#     permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser
#
#     def get(self, request):
#         query_params = request.query_params
#         try:
#             start_date_str = query_params.get('start_date')
#             end_date_str = query_params.get('end_date')
#             if not start_date_str: raise ValueError("'start_date' parametri majburiy.")
#             if not end_date_str: raise ValueError("'end_date' parametri majburiy.")
#
#             start_date = parse_date(start_date_str)
#             end_date = parse_date(end_date_str)
#             if not start_date or not end_date: raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD).")
#             if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
#
#             currency = query_params.get('currency', 'UZS').upper()
#             if currency not in ['UZS', 'USD']: raise ValueError("Valyuta 'UZS' yoki 'USD' bo'lishi kerak.")
#
#             category_id = query_params.get('category_id')
#             if category_id: category_id = int(category_id)
#
#             report_data = get_products_report_data(
#                 start_date=start_date, end_date=end_date,
#                 currency=currency, category_id=category_id
#             )
#             return Response(report_data)
#
#         except (ValueError, TypeError) as e:
#              return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             print(f"!!! ERROR generating Products Report: {e}"); traceback.print_exc()
#             return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#
# class SellersReportView(views.APIView):
#     """Sotuvchilar hisoboti uchun API view (Alohida)"""
#     permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser
#
#     def get(self, request):
#         query_params = request.query_params
#         try:
#             start_date_str = query_params.get('start_date')
#             end_date_str = query_params.get('end_date')
#             if not start_date_str: raise ValueError("'start_date' parametri majburiy.")
#             if not end_date_str: raise ValueError("'end_date' parametri majburiy.")
#
#             start_date = parse_date(start_date_str)
#             end_date = parse_date(end_date_str)
#             if not start_date or not end_date: raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD).")
#             if start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
#
#             currency = query_params.get('currency', 'UZS').upper()
#             if currency not in ['UZS', 'USD']: raise ValueError("Valyuta 'UZS' yoki 'USD' bo'lishi kerak.")
#
#             report_data = get_sellers_report_data(
#                 start_date=start_date, end_date=end_date, currency=currency
#             )
#             return Response(report_data)
#
#         except (ValueError, TypeError) as e:
#              return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             print(f"!!! ERROR generating Sellers Report: {e}"); traceback.print_exc()
#             return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
#
#
# class InstallmentsReportView(views.APIView):
#     """Nasiyalar hisoboti uchun API view (Alohida)"""
#     permission_classes = [permissions.IsAuthenticated] # Yoki IsAdminUser
#
#     def get(self, request):
#         query_params = request.query_params
#         try:
#             # Sanalar ixtiyoriy
#             start_date_str = query_params.get('start_date')
#             end_date_str = query_params.get('end_date')
#             start_date = parse_date(start_date_str) if start_date_str else None
#             end_date = parse_date(end_date_str) if end_date_str else None
#             if start_date and end_date and start_date > end_date: raise ValueError("Boshlanish sanasi tugash sanasidan keyin.")
#
#             customer_id = query_params.get('customer_id')
#             if customer_id: customer_id = int(customer_id)
#
#             status = query_params.get('status')
#             if status and status not in InstallmentPlan.PlanStatus.values: raise ValueError("Noto'g'ri status qiymati.")
#
#             report_data = get_installments_report_data(
#                 start_date=start_date, end_date=end_date,
#                 customer_id=customer_id, status=status
#             )
#             return Response(report_data)
#
#         except (ValueError, TypeError) as e:
#              return Response({"error": f"Parametr xatoligi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             print(f"!!! ERROR generating Installments Report: {e}"); traceback.print_exc()
#             return Response({"error": "Hisobot yaratishda ichki xatolik."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# reports/views.py
from rest_framework import views, status, permissions
from rest_framework.response import Response
# from django.utils.dateparse import parse_date # Endi kerak emas, servis qiladi
from django.utils import timezone
from datetime import timedelta

from .services import (
    get_dashboard_stats, get_sales_report_data, get_products_report_data,
    get_sellers_report_data, get_installments_report_data,
    get_inventory_stock_report, get_inventory_history_report
)
from products.models import Kassa


class BaseReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]  # Yoki IsAdminUser
    data_service = None

    # required_params va optional_params endi boshqacha ishlaydi

    def get_common_params(self, request):
        """Umumiy query parametrlarni oladi (period_type, start_date, end_date)"""
        params = {}
        params['period_type'] = request.query_params.get('period_type', 'daily').lower()  # Default 'daily'

        if params['period_type'] not in ['daily', 'weekly', 'monthly', 'custom', 'all_time']:
            raise ValueError(f"Noto'g'ri 'period_type' qiymati: {params['period_type']}.")

        if params['period_type'] == 'custom':
            params['start_date_str'] = request.query_params.get('start_date')
            params['end_date_str'] = request.query_params.get('end_date')
            if not params['start_date_str'] or not params['end_date_str']:
                raise ValueError("Custom period uchun 'start_date' va 'end_date' query parametrlari majburiy.")
        else:
            params['start_date_str'] = None
            params['end_date_str'] = None

        return params

    def get(self, request):
        try:
            common_params = self.get_common_params(request)
            # Har bir view o'ziga kerakli qo'shimcha parametrlarni params ga qo'shadi
            # va data_service ga uzatadi
            service_params = common_params.copy()  # Asosiy parametrlarni nusxalash
            self.extract_extra_params(request, service_params)  # Qo'shimcha parametrlarni olish

        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)

        if not self.data_service:
            return Response({"error": "Hisobot xizmati aniqlanmagan."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            report_data = self.data_service(**service_params)
            return Response(report_data)
        except ValueError as ve_service:  # Servisdagi validatsiya xatolari (masalan, noto'g'ri valyuta)
            return Response({"error": str(ve_service)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error generating report ({self.data_service.__name__}): {e}")
            import traceback
            print(traceback.format_exc())
            return Response({"error": "Hisobot yaratishda ichki xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def extract_extra_params(self, request, params):
        """Subklasslarda override qilinadi, params lug'atini to'ldiradi."""
        pass


class DashboardStatsView(views.APIView):  # BaseReportView dan meros olmaydi
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        kassa_id_str = request.query_params.get('kassa_id')
        final_kassa_id = None
        if kassa_id_str:
            try:
                final_kassa_id = int(kassa_id_str)
            except ValueError:
                return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)
        else:  # Default kassa
            first_kassa = Kassa.objects.filter(is_active=True).first()
            if first_kassa: final_kassa_id = first_kassa.id

        period_type = request.query_params.get('period_type', 'all').lower()  # Dashboard uchun default 'all'
        if period_type not in ['daily', 'monthly', 'all', 'all_time']:  # Dashboard 'weekly' ni alohida qabul qilmaydi
            return Response({"error": "Noto'g'ri 'period_type' qiymati dashboard uchun."},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            stats = get_dashboard_stats(kassa_id=final_kassa_id, period_type=period_type)
            return Response(stats)
        except Exception as e:
            print(f"!!! ERROR in DashboardStatsView: {e}")
            import traceback;
            print(traceback.format_exc())
            return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesReportView(BaseReportView):
    data_service = get_sales_report_data

    def extract_extra_params(self, request, params):  # params bu yerda common_params ni o'z ichiga oladi
        params['currency'] = request.query_params.get('currency', 'UZS').upper()
        params['seller_id'] = request.query_params.get('seller_id')
        params['kassa_id'] = request.query_params.get('kassa_id')
        params['payment_type'] = request.query_params.get('payment_type')
        params['group_by'] = request.query_params.get('group_by')


class ProductsReportView(BaseReportView):
    data_service = get_products_report_data

    def extract_extra_params(self, request, params):
        params['currency'] = request.query_params.get('currency', 'UZS').upper()
        params['category_id'] = request.query_params.get('category_id')


class SellersReportView(BaseReportView):
    data_service = get_sellers_report_data

    def extract_extra_params(self, request, params):
        params['currency'] = request.query_params.get('currency', 'UZS').upper()


class InstallmentsReportView(BaseReportView):
    data_service = get_installments_report_data

    # Bu hisobot uchun period_type 'all_time' bo'lishi mumkin (agar sana berilmasa)
    def get_common_params(self, request):  # Override qilib, default 'all_time' qilamiz
        params = {}
        params['period_type'] = request.query_params.get('period_type', 'all_time').lower()
        if params['period_type'] not in ['daily', 'weekly', 'monthly', 'custom', 'all_time']:
            raise ValueError(f"Noto'g'ri 'period_type' qiymati: {params['period_type']}.")
        if params['period_type'] == 'custom':
            params['start_date_str'] = request.query_params.get('start_date')
            params['end_date_str'] = request.query_params.get('end_date')
            if not params['start_date_str'] or not params['end_date_str']:
                raise ValueError("Custom period uchun 'start_date' va 'end_date' majburiy.")
        else:
            params['start_date_str'] = None
            params['end_date_str'] = None
        return params

    def extract_extra_params(self, request, params):
        params['customer_id'] = request.query_params.get('customer_id')
        params['status'] = request.query_params.get('status')
        params['currency_filter'] = request.query_params.get('currency_filter')


class InventoryStockReportView(BaseReportView):
    data_service = get_inventory_stock_report

    # Bu hisobot sana oralig'iga bog'liq emas
    def get_common_params(self, request): return {}  # Sana parametrlarini olmaymiz

    def extract_extra_params(self, request, params):
        params['kassa_id'] = request.query_params.get('kassa_id')
        params['category_id'] = request.query_params.get('category_id')
        params['low_stock_only'] = request.query_params.get('low_stock_only', 'false').lower() == 'true'


class InventoryHistoryReportView(BaseReportView):
    data_service = get_inventory_history_report

    # Bu hisobot sana oralig'iga bog'liq
    def extract_extra_params(self, request, params):  # common_params allaqachon period va sanalarni o'z ichiga oladi
        params['kassa_id'] = request.query_params.get('kassa_id')
        params['product_id'] = request.query_params.get('product_id')
        params['user_id'] = request.query_params.get('user_id')
        params['operation_type'] = request.query_params.get('operation_type')