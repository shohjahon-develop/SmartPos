# reports/views.py
from rest_framework import views, status, permissions
from rest_framework.response import Response
from django.utils import timezone  # Dashboard uchun
from datetime import timedelta  # Dashboard uchun

from .services import (
    get_dashboard_stats, get_sales_report_data, get_products_report_data,
    get_sellers_report_data, get_installments_report_data,
    get_inventory_stock_report, get_inventory_history_report
)
from products.models import Kassa
from sales.models import Sale
from installments.models import InstallmentPlan  # Validatsiya uchun


class DashboardStatsView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]  # Yoki IsAdminUser

    def get(self, request):
        kassa_id_str = request.query_params.get('kassa_id')
        final_kassa_id = None
        if kassa_id_str:
            try:
                final_kassa_id = int(kassa_id_str)
                if not Kassa.objects.filter(pk=final_kassa_id, is_active=True).exists():
                    return Response({"error": f"ID={final_kassa_id} bilan aktiv kassa topilmadi."},
                                    status=status.HTTP_404_NOT_FOUND)
            except ValueError:
                return Response({"error": "Noto'g'ri kassa ID formati."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            first_kassa = Kassa.objects.filter(is_active=True).first()
            if first_kassa: final_kassa_id = first_kassa.id

        period_type = request.query_params.get('period_type', 'all').lower()
        if period_type not in ['daily', 'monthly', 'all']:
            return Response({"error": "Noto'g'ri 'period_type' qiymati ('daily', 'monthly', 'all')."},
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