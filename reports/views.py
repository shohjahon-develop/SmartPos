# reports/views.py
from rest_framework import views, status, permissions
from rest_framework.response import Response
from django.utils import timezone  # Dashboard uchun
from datetime import timedelta  # Dashboard uchun

from .services import *
from products.models import Kassa
from sales.models import Sale
from installments.models import InstallmentPlan  # Validatsiya uchun


# class DashboardStatsView(views.APIView):
#     permission_classes = [permissions.IsAuthenticated]  # Yoki IsAdminUser
#
#     def get(self, request):
#         kassa_id_str = request.query_params.get('kassa_id')
#         final_kassa_id = None
#         if kassa_id_str:
#             try:
#                 final_kassa_id = int(kassa_id_str)
#                 if not Kassa.objects.filter(pk=final_kassa_id, is_active=True).exists():
#                     return Response({"error": f"ID={final_kassa_id} bilan aktiv kassa topilmadi."},
#                                     status=status.HTTP_404_NOT_FOUND)
#             except ValueError:
#                 return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)
#         else:
#             first_kassa = Kassa.objects.filter(is_active=True).first()
#             if first_kassa: final_kassa_id = first_kassa.id
#
#         period_type = request.query_params.get('period_type', 'all').lower()
#         if period_type not in ['daily', 'monthly', 'all']:
#             return Response({"error": "Noto'g'ri 'period_type' qiymati ('daily', 'monthly', 'all')."},
#                             status=status.HTTP_400_BAD_REQUEST)
#
#         try:
#             stats = get_dashboard_stats(kassa_id=final_kassa_id, period_type=period_type)
#             return Response(stats)
#         except Exception as e:
#             print(f"!!! ERROR in DashboardStatsView: {e}")
#             import traceback;
#             print(traceback.format_exc())
#             return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."},
#                             status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class DashboardStatsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        kassa_id_str = qp.get('kassa_id')
        target_date_str = qp.get('date')  # YYYY-MM-DD formatida
        target_month_str = qp.get('month')  # YYYY-MM formatida
        # period_type 'all', 'daily', 'monthly' bo'lishi mumkin, agar date/month berilmasa
        period_type = qp.get('period_type', 'all').lower()

        final_kassa_id = None
        if kassa_id_str:
            try:
                final_kassa_id = int(kassa_id_str)
                if not Kassa.objects.filter(pk=final_kassa_id, is_active=True).exists():
                    return Response({"error": f"ID={final_kassa_id} bilan aktiv kassa topilmadi."},
                                    status=status.HTTP_404_NOT_FOUND)
            except ValueError:
                return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)
        else:  # Agar kassa ID berilmasa, birinchi aktiv kassani olish (ixtiyoriy)
            first_kassa = Kassa.objects.filter(is_active=True).order_by('id').first()
            if first_kassa: final_kassa_id = first_kassa.id

        try:
            # Agar date yoki month berilgan bo'lsa, period_type ni e'tiborsiz qoldirish mumkin yoki
            # period_type ni ham hisobga olish kerak. Hozircha, date/month ustunroq.
            stats = get_dashboard_stats(
                kassa_id=final_kassa_id,
                target_date_str=target_date_str,
                target_month_str=target_month_str,
                period_type=period_type if not (target_date_str or target_month_str) else 'all'
                # Agar sana/oy berilsa, 'all' kabi ishlaydi
            )
            return Response(stats)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"!!! ERROR in DashboardStatsView: {e}")
            import traceback;
            traceback.print_exc()
            return Response({"error": "Dashboard ma'lumotlarini olishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SalesChartView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            # period_type endi guruhlash intervalini bildiradi: 'daily', 'weekly', 'monthly'
            # Agar sana oralig'i berilmasa, bu standart davrni ham bildiradi.
            group_by_interval = qp.get('period_type', 'monthly').lower()
            currency = qp.get('currency', 'UZS').upper()
            kassa_id_str = qp.get('kassa_id')
            start_date_str = qp.get('start_date')  # YYYY-MM-DD
            end_date_str = qp.get('end_date')  # YYYY-MM-DD

            final_kassa_id = None
            if kassa_id_str:
                try:
                    final_kassa_id = int(kassa_id_str)
                except ValueError:
                    return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)

            # Agar faqat start_date berilsa, end_date ham o'sha kunga teng bo'ladi (servisda)
            # Agar hech qanday sana berilmasa, period_type (group_by_interval) standart davrni belgilaydi

            chart_data = get_sales_chart_data(
                period_type=group_by_interval,  # Bu guruhlash uchun
                currency=currency,
                kassa_id=final_kassa_id,
                start_date_str=start_date_str,
                end_date_str=end_date_str
            )
            return Response(chart_data)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in SalesChartView: {e}");
            import traceback;
            traceback.print_exc()
            return Response({"error": "Sotuvlar grafigi ma'lumotlarini olishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SalesReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            period_type = qp.get('period_type', 'daily').lower()
            start_date_str = qp.get('start_date')
            end_date_str = qp.get('end_date')
            currency = qp.get('currency', 'UZS').upper()

            report_data = get_sales_report_data(
                period_type=period_type, start_date_str=start_date_str, end_date_str=end_date_str,
                currency=currency, seller_id=qp.get('seller_id'), kassa_id=qp.get('kassa_id'),
                payment_type=qp.get('payment_type'), group_by=qp.get('group_by')
            )
            return Response(report_data)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in SalesReportView: {e}");
            import traceback;
            traceback.print_exc()
            return Response({"error": "Sotuvlar hisobotini yaratishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProductsReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            period_type = qp.get('period_type', 'monthly').lower()
            start_date_str = qp.get('start_date')
            end_date_str = qp.get('end_date')
            currency = qp.get('currency', 'UZS').upper()

            report_data = get_products_report_data(
                period_type=period_type, start_date_str=start_date_str, end_date_str=end_date_str,
                currency=currency, category_id=qp.get('category_id')
            )
            return Response(report_data)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in ProductsReportView: {e}");
            import traceback;
            traceback.print_exc()
            return Response({"error": "Mahsulotlar hisobotini yaratishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# class SellersReportView(views.APIView):
#     permission_classes = [permissions.IsAuthenticated]
#
#     def get(self, request):
#         qp = request.query_params
#         try:
#             period_type = qp.get('period_type', 'monthly').lower()
#             start_date_str = qp.get('start_date')
#             end_date_str = qp.get('end_date')
#             currency = qp.get('currency', 'UZS').upper()
#
#             report_data = get_sellers_report_data(
#                 period_type=period_type, start_date_str=start_date_str, end_date_str=end_date_str,
#                 currency=currency
#             )
#             return Response(report_data)
#         except ValueError as ve:
#             return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             print(f"Error in SellersReportView: {e}");
#             import traceback;
#             traceback.print_exc()
#             return Response({"error": "Sotuvchilar hisobotini yaratishda xatolik."},
#                             status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InstallmentsReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            period_type = qp.get('period_type', 'all_time').lower()
            start_date_str = qp.get('start_date')
            end_date_str = qp.get('end_date')
            currency_filter = qp.get('currency_filter')
            if currency_filter: currency_filter = currency_filter.upper()

            report_data = get_installments_report_data(
                period_type=period_type, start_date_str=start_date_str, end_date_str=end_date_str,
                customer_id=qp.get('customer_id'), status=qp.get('status'), currency_filter=currency_filter
            )
            return Response(report_data)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in InstallmentsReportView: {e}");
            import traceback;
            traceback.print_exc()
            return Response({"error": "Nasiyalar hisobotini yaratishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InventoryStockReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            report_data = get_inventory_stock_report(
                kassa_id=qp.get('kassa_id'),
                category_id=qp.get('category_id'),
                low_stock_only=qp.get('low_stock_only', 'false').lower() == 'true'
            )
            return Response(report_data)
        except ValueError as ve:  # Servisdagi validatsiya xatolari uchun
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in InventoryStockReportView: {e}");
            import traceback;
            traceback.print_exc()
            return Response({"error": "Ombor qoldiqlari hisobotini yaratishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InventoryHistoryReportView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            period_type = qp.get('period_type', 'daily').lower()
            start_date_str = qp.get('start_date')
            end_date_str = qp.get('end_date')

            report_data = get_inventory_history_report(
                period_type=period_type, start_date_str=start_date_str, end_date_str=end_date_str,
                kassa_id=qp.get('kassa_id'), product_id=qp.get('product_id'),
                user_id=qp.get('user_id'), operation_type=qp.get('operation_type')
            )
            return Response(report_data)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in InventoryHistoryReportView: {e}");
            import traceback;
            traceback.print_exc()
            return Response({"error": "Ombor tarixi hisobotini yaratishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# YANGI VIEW: Sotuvlar grafigi uchun
class SalesChartView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qp = request.query_params
        try:
            period_type = qp.get('period_type', 'monthly').lower() # Default 'monthly'
            currency = qp.get('currency', 'UZS').upper()           # Default 'UZS'
            kassa_id_str = qp.get('kassa_id')

            final_kassa_id = None
            if kassa_id_str:
                try:
                    final_kassa_id = int(kassa_id_str)
                    # Kassa mavjudligini tekshirish (ixtiyoriy, lekin yaxshi amaliyot)
                    if not Kassa.objects.filter(pk=final_kassa_id, is_active=True).exists():
                        return Response({"error": f"ID={final_kassa_id} bilan aktiv kassa topilmadi."},
                                        status=status.HTTP_404_NOT_FOUND)
                except ValueError:
                    return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)

            chart_data = get_sales_chart_data(
                period_type=period_type,
                currency=currency,
                kassa_id=final_kassa_id
            )
            return Response(chart_data)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error in SalesChartView: {e}")
            import traceback
            traceback.print_exc()
            return Response({"error": "Sotuvlar grafigi ma'lumotlarini olishda xatolik."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)