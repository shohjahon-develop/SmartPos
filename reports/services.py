# reports/services.py
import calendar

from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast, Coalesce
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

# Model importlari
from users.models import User, UserProfile
from sales.models import Sale, SaleItem, Customer, KassaTransaction, Kassa  # SaleCurrency endi Sale orqali olinadi
from products.models import Product, Category
from inventory.models import ProductStock, InventoryOperation
from installments.models import InstallmentPlan, InstallmentPayment

# reports/services.py
from django.db.models import Sum, Count, F, DecimalField, Q, Value, Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

# Model importlari
from users.models import User, UserProfile
from sales.models import *
from products.models import Product, Category
from inventory.models import ProductStock, InventoryOperation
from installments.models import InstallmentPlan, InstallmentPayment


# --- YORDAMCHI FUNKSIYA: DAVR BO'YICHA SANA ORALIG'INI OLISH (O'zgarishsiz) ---
def get_date_range_from_period(period_type, start_date_str=None, end_date_str=None):
    # ... (avvalgi kod) ...
    today = timezone.now().date()
    start_date, end_date = None, None
    period_type = period_type.lower() if period_type else 'all_time' # yoki 'monthly' default
    if period_type == 'daily':
        start_date = end_date = today
    elif period_type == 'weekly':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period_type == 'monthly':
        start_date = today.replace(day=1)
        # Oyning oxirgi kunini to'g'ri topish
        _, last_day_of_month = calendar.monthrange(today.year, today.month)
        end_date = today.replace(day=last_day_of_month)
    elif period_type == 'custom':
        if not start_date_str or not end_date_str: raise ValueError("Custom uchun 'start_date'/'end_date' majburiy.")
        try:
            start_date, end_date = date.fromisoformat(start_date_str), date.fromisoformat(end_date_str)
        except ValueError as e:
            raise ValueError(f"Sana formati xato (YYYY-MM-DD): {e}")
        if start_date > end_date: raise ValueError("Boshlanish sanasi tugashdan keyin.")
    elif period_type == 'all_time':
        end_date = today
    else: # Default 'monthly' yoki xatolik
        # Agar notanish period_type kelsa, default 'monthly' ni ishlatamiz yoki xatolik beramiz
        # Hozircha xatolik beramiz, chunki sales_chart uchun aniq periodlar kerak
        raise ValueError(f"Noto'g'ri 'period_type': {period_type}. Mumkin: 'daily', 'weekly', 'monthly'.")
    return start_date, end_date


def get_kassa_balance_currency(kassa_id, currency_code):
    """Belgilangan kassa va valyuta uchun balansni hisoblaydi."""
    try:
        kassa = Kassa.objects.get(pk=kassa_id)

        # Kirim turlari (shu valyutada)
        income_transaction_types = [
            KassaTransaction.TransactionType.SALE,
            KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
            KassaTransaction.TransactionType.CASH_IN,
            KassaTransaction.TransactionType.EXCHANGE_BUY_CURRENCY  # Bu valyuta olinganda
        ]
        # Chiqim turlari (shu valyutada)
        expense_transaction_types = [
            KassaTransaction.TransactionType.CASH_OUT,
            KassaTransaction.TransactionType.RETURN_REFUND,
            KassaTransaction.TransactionType.EXCHANGE_SELL_CURRENCY  # Bu valyuta sotilganda
        ]

        balance_agg = KassaTransaction.objects.filter(kassa=kassa, currency=currency_code).aggregate(
            total_income=Sum(
                Case(When(transaction_type__in=income_transaction_types, then=F('amount')), default=Value(Decimal(0))),
                output_field=DecimalField(decimal_places=2)
            ),
            total_expense=Sum(
                Case(When(transaction_type__in=expense_transaction_types, then=F('amount')), default=Value(Decimal(0))),
                output_field=DecimalField(decimal_places=2)
            )
        )
        income = balance_agg.get('total_income') or Decimal(0)
        expense = balance_agg.get('total_expense') or Decimal(0)
        return income - expense
    except Kassa.DoesNotExist:
        print(f"Kassa topilmadi: ID={kassa_id}")
        return Decimal(0)  # Yoki None qaytarish xatolikni bildirish uchun
    except Exception as e:
        print(f"Balans hisoblashda xato (Kassa ID: {kassa_id}, Valyuta: {currency_code}): {e}")
        return None  # Xatolik yuz berdi



# def get_dashboard_stats(kassa_id=None, period_type='all'):
#     today = timezone.now().date()
#     results = {}
#     # Sotuv statuslari: Faqat yakunlangan yoki qisman qaytarilganlarni olamiz
#     # Qaytarilgan tovarlar uchun foydani to'g'ri hisoblash uchun qo'shimcha logika kerak bo'lishi mumkin
#     # Hozircha, SaleItem dagi quantity ni (qaytarilmagan qoldiqni emas) ishlatamiz,
#     # lekin ideal holatda qaytarilganlarni ayirish kerak.
#     # Yoki Sale.status='COMPLETED' bo'lganlarni olib, SaleReturn orqali ayirish.
#     # Sodda yondashuv: Faqat COMPLETED sotuvlar.
#     base_sales_filter_for_profit = Q(status=Sale.SaleStatus.COMPLETED)  # Faqat to'liq yakunlangan sotuvlar
#
#     # Agar qisman qaytarilganlarni ham hisobga olmoqchi bo'lsak:
#     # base_sales_filter_for_profit = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
#     # Lekin bunda SaleItem.quantity_available_to_return ni ishlatish kerak bo'ladi. Hozircha soddalashtiramiz.
#
#     kassa_q_filter_sale = Q(kassa_id=kassa_id) if kassa_id else Q()
#
#     # Nasiya to'lovlari sof foydaga ta'sir qilmaydi, shuning uchun ularni alohida hisoblamaymiz.
#     # Sof foyda sotuvning o'zidan keladi.
#
#     # --- Sof Foydani Hisoblash Uchun Yordamchi Funksiya ---
#     def calculate_net_profit_for_sales(sales_queryset):
#         net_profit_uzs = Decimal(0)
#         net_profit_usd = Decimal(0)
#
#         for sale in sales_queryset.prefetch_related('items__product'):  # product ni prefetch qilamiz
#             for item in sale.items.all():
#                 # Agar SaleItem da qaytarilgan miqdorni hisobga oladigan bo'lsak:
#                 # actual_sold_quantity = item.quantity - item.quantity_returned
#                 # if actual_sold_quantity <= 0:
#                 #     continue
#                 actual_sold_quantity = item.quantity  # Hozircha to'liq miqdorni olamiz (COMPLETED status uchun)
#
#                 if sale.currency == Sale.SaleCurrency.UZS:
#                     selling_price_per_unit = item.price_at_sale_uzs or Decimal(0)
#                     cost_price_per_unit = item.product.purchase_price_uzs or Decimal(0)  # Mahsulotning UZS tan narxi
#                     if item.product.purchase_price_uzs is None and item.product.purchase_price_usd is not None:
#                         # Agar UZS tan narxi yo'q, lekin USD bor bo'lsa va kurs bo'lsa, konvertatsiya qilish mumkin
#                         # Hozircha, agar UZS tan narxi yo'q bo'lsa, foyda 0 deb hisoblaymiz (yoki xatolik berish)
#                         # Bu joyni kurs bilan ishlashga moslashtirish kerak bo'ladi. Hozircha sodda.
#                         # print(f"Warning: UZS cost price not found for product {item.product.name}, UZS profit might be inaccurate.")
#                         pass  # Yoki cost_price_per_unit = selling_price_per_unit qilib foydani 0 qilish
#
#                     profit_per_unit = selling_price_per_unit - cost_price_per_unit
#                     net_profit_uzs += profit_per_unit * actual_sold_quantity
#
#                 elif sale.currency == Sale.SaleCurrency.USD:
#                     selling_price_per_unit = item.price_at_sale_usd or Decimal(0)
#                     cost_price_per_unit = item.product.purchase_price_usd or Decimal(0)  # Mahsulotning USD tan narxi
#                     if item.product.purchase_price_usd is None:
#                         # print(f"Warning: USD cost price not found for product {item.product.name}, USD profit might be inaccurate.")
#                         pass
#                     profit_per_unit = selling_price_per_unit - cost_price_per_unit
#                     net_profit_usd += profit_per_unit * actual_sold_quantity
#         return net_profit_uzs, net_profit_usd
#
#     # --- Kunlik Statistikalar (Sof foyda bilan) ---
#     if period_type == 'daily' or period_type == 'all':
#         # ... (kunlik UZS/USD tushumlar va sotuvlar soni avvalgidek) ...
#         # Bu qism o'zgarishsiz qoladi, chunki bu kassaga tushgan pulni ko'rsatadi.
#         s_uzs_today_paid = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.UZS) & Q(created_at__date=today)).aggregate(
#             paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
#         daily_sales_uzs_count = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.UZS) & Q(created_at__date=today)).count()
#         s_usd_today_paid = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.USD) & Q(created_at__date=today)).aggregate(
#             paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
#         daily_sales_usd_count = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.USD) & Q(created_at__date=today)).count()
#         i_uzs_today_paid = InstallmentPayment.objects.filter(
#             Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(
#                 payment_date__date=today)).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)
#         i_usd_today_paid = InstallmentPayment.objects.filter(
#             Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.USD) & Q(
#                 payment_date__date=today)).aggregate(paid=Sum('amount', default=Decimal(0)))['paid'] or Decimal(0)
#
#         results['today_cashflow_uzs'] = s_uzs_today_paid + i_uzs_today_paid  # Kassaga tushgan pul
#         results['today_sales_uzs_count'] = daily_sales_uzs_count
#         results['today_cashflow_usd'] = s_usd_today_paid + i_usd_today_paid  # Kassaga tushgan pul
#         results['today_sales_usd_count'] = daily_sales_usd_count
#         results['today_total_sales_count'] = daily_sales_uzs_count + daily_sales_usd_count
#
#         # Kunlik sof foyda
#         daily_sales_for_profit = Sale.objects.filter(
#             base_sales_filter_for_profit & kassa_q_filter_sale & Q(created_at__date=today))
#         daily_net_profit_uzs, daily_net_profit_usd = calculate_net_profit_for_sales(daily_sales_for_profit)
#         results['today_net_profit_uzs'] = daily_net_profit_uzs  # YANGI
#         results['today_net_profit_usd'] = daily_net_profit_usd  # YANGI
#
#     # --- Oylik Statistikalar (Sof foyda bilan) ---
#     if period_type == 'monthly' or period_type == 'all':
#         start_of_month = today.replace(day=1)
#         # ... (oylik UZS/USD tushumlar va sotuvlar soni avvalgidek) ...
#         s_uzs_month_paid = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.UZS) & Q(created_at__date__gte=start_of_month)).aggregate(
#             paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
#         monthly_sales_uzs_count = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.UZS) & Q(created_at__date__gte=start_of_month)).count()
#         s_usd_month_paid = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.USD) & Q(created_at__date__gte=start_of_month)).aggregate(
#             paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid'] or Decimal(0)
#         monthly_sales_usd_count = Sale.objects.filter(
#             Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & kassa_q_filter_sale & Q(
#                 currency=Sale.SaleCurrency.USD) & Q(created_at__date__gte=start_of_month)).count()
#         i_uzs_month_paid = InstallmentPayment.objects.filter(
#             Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(
#                 payment_date__date__gte=start_of_month)).aggregate(paid=Sum('amount', default=Decimal(0)))[
#                                'paid'] or Decimal(0)
#         i_usd_month_paid = InstallmentPayment.objects.filter(
#             Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.USD) & Q(
#                 payment_date__date__gte=start_of_month)).aggregate(paid=Sum('amount', default=Decimal(0)))[
#                                'paid'] or Decimal(0)
#
#         results['monthly_cashflow_uzs'] = s_uzs_month_paid + i_uzs_month_paid  # Kassaga tushgan pul
#         results['monthly_sales_uzs_count'] = monthly_sales_uzs_count
#         results['monthly_cashflow_usd'] = s_usd_month_paid + i_usd_month_paid  # Kassaga tushgan pul
#         results['monthly_sales_usd_count'] = monthly_sales_usd_count
#         results['monthly_total_sales_count'] = monthly_sales_uzs_count + monthly_sales_usd_count
#
#         # Oylik sof foyda
#         monthly_sales_for_profit = Sale.objects.filter(
#             base_sales_filter_for_profit & kassa_q_filter_sale & Q(created_at__date__gte=start_of_month))
#         monthly_net_profit_uzs, monthly_net_profit_usd = calculate_net_profit_for_sales(monthly_sales_for_profit)
#         results['monthly_net_profit_uzs'] = monthly_net_profit_uzs  # YANGI
#         results['monthly_net_profit_usd'] = monthly_net_profit_usd  # YANGI
#
#     # --- Umumiy Statistikalar ('all' uchun) ---
#     if period_type == 'all':
#         # ... (total_products, low_stock_products, customers, va hokazo avvalgidek) ...
#         results['total_products'] = Product.objects.filter(is_active=True).count()
#         accessory_categories_for_low_stock = Category.objects.filter(is_accessory_category=True)
#         results['low_stock_products'] = ProductStock.objects.filter(quantity__lte=F('minimum_stock_level'),
#                                                                     product__category__in=accessory_categories_for_low_stock).count()
#         results['total_customers'] = Customer.objects.count()
#         results['new_customers_today'] = Customer.objects.filter(created_at__date=today).count()
#         thirty_days_ago = today - timedelta(days=30)
#         top_products = SaleItem.objects.filter(sale__created_at__date__gte=thirty_days_ago,
#                                                sale__status__in=[Sale.SaleStatus.COMPLETED,
#                                                                  Sale.SaleStatus.PARTIALLY_RETURNED]).values(
#             'product__name').annotate(total_quantity_sold=Sum('quantity')).order_by('-total_quantity_sold')[:5]
#         results['top_products_chart'] = list(top_products)
#
#     # --- Kassa Balanslari ---
#     if kassa_id:
#         results['kassa_balance_uzs'] = get_kassa_balance_currency(kassa_id, Sale.SaleCurrency.UZS)
#         results['kassa_balance_usd'] = get_kassa_balance_currency(kassa_id, Sale.SaleCurrency.USD)
#         try:
#             results['kassa_name'] = Kassa.objects.get(pk=kassa_id).name
#         except Kassa.DoesNotExist:
#             results['kassa_name'] = None
#     else:
#         results['kassa_balance_uzs'] = None
#         results['kassa_balance_usd'] = None
#         results['kassa_name'] = "Umumiy"
#     return results
def get_dashboard_stats(kassa_id=None, target_date_str=None, target_month_str=None,
                        period_type='all'):  # period_type qoladi, agar target_date/month bo'lmasa
    """
    Dashboard statistikalarini hisoblaydi.
    target_date_str: YYYY-MM-DD formatida, kunlik statistika uchun.
    target_month_str: YYYY-MM formatida, oylik statistika uchun.
    period_type: Agar target_date/month berilmasa, 'daily', 'monthly', 'all' ishlatiladi.
    """
    results = {}

    current_day_for_calc = timezone.now().date()
    target_date_for_daily_stats = current_day_for_calc

    if target_date_str:
        try:
            target_date_for_daily_stats = date.fromisoformat(target_date_str)
        except ValueError:
            # Agar sana formati noto'g'ri bo'lsa, joriy kunni ishlatamiz yoki xatolik beramiz
            print(f"WARNING: Noto'g'ri target_date_str formati: {target_date_str}. Joriy kun ishlatiladi.")
            # raise ValueError(f"Noto'g'ri sana formati: {target_date_str}. YYYY-MM-DD bo'lishi kerak.")

    # Oylik statistika uchun boshlanish va tugash sanalarini aniqlash
    if target_month_str:
        try:
            year, month = map(int, target_month_str.split('-'))
            start_of_target_month = date(year, month, 1)
            _, last_day_of_target_month = calendar.monthrange(year, month)
            end_of_target_month = date(year, month, last_day_of_target_month)
        except ValueError:
            print(f"WARNING: Noto'g'ri target_month_str formati: {target_month_str}. Joriy oy ishlatiladi.")
            start_of_target_month = current_day_for_calc.replace(day=1)
            _, last_day_of_current_month = calendar.monthrange(current_day_for_calc.year, current_day_for_calc.month)
            end_of_target_month = current_day_for_calc.replace(day=last_day_of_current_month)
    else:  # Agar target_month_str berilmasa, joriy oyni olamiz
        start_of_target_month = current_day_for_calc.replace(day=1)
        _, last_day_of_current_month = calendar.monthrange(current_day_for_calc.year, current_day_for_calc.month)
        end_of_target_month = current_day_for_calc.replace(day=last_day_of_current_month)

    # --- Umumiy filtrlar ---
    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    base_sales_filter_for_profit = Q(status=Sale.SaleStatus.COMPLETED)  # Sof foyda uchun
    kassa_q_filter_sale = Q(kassa_id=kassa_id) if kassa_id else Q()

    # --- Yordamchi funksiya (sof foyda uchun, avvalgidek) ---
    def calculate_net_profit_for_sales(sales_queryset):
        net_profit_uzs = Decimal(0);
        net_profit_usd = Decimal(0)
        for sale in sales_queryset.prefetch_related('items__product'):
            for item in sale.items.all():
                actual_sold_quantity = item.quantity  # Yoki item.quantity - item.quantity_returned
                if actual_sold_quantity <= 0: continue
                if sale.currency == Sale.SaleCurrency.UZS:
                    sp = item.price_at_sale_uzs or Decimal(0)
                    cp = item.product.purchase_price_uzs if item.product.purchase_price_uzs is not None else sp  # Agar tan narx yo'q bo'lsa, foyda 0
                    net_profit_uzs += (sp - cp) * actual_sold_quantity
                elif sale.currency == Sale.SaleCurrency.USD:
                    sp = item.price_at_sale_usd or Decimal(0)
                    cp = item.product.purchase_price_usd if item.product.purchase_price_usd is not None else sp
                    net_profit_usd += (sp - cp) * actual_sold_quantity
        return net_profit_uzs, net_profit_usd

    # --- "Kunlik" (target_date_for_daily_stats uchun) Statistikalar ---
    # Bu qism har doim hisoblanadi va 'today_...' kalitlari bilan qaytariladi,
    # lekin nomi "target_day_..." bo'lishi mantiqan to'g'riroq. Hozircha nomini o'zgartirmaymiz.

    # Kassaga tushgan pul (target_date uchun)
    s_uzs_target_day = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
            created_at__date=target_date_for_daily_stats)).aggregate(
        paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid']
    daily_sales_uzs_c = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
            created_at__date=target_date_for_daily_stats)).count()
    s_usd_target_day = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.USD) & Q(
            created_at__date=target_date_for_daily_stats)).aggregate(
        paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid']
    daily_sales_usd_c = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.USD) & Q(
            created_at__date=target_date_for_daily_stats)).count()

    # Nasiyadan tushumlar (target_date uchun) - bu qismni soddalashtirish yoki aniqlashtirish kerak
    # Hozircha, nasiya tushumlari sof foydaga kirmaydi, faqat kassaga tushgan pulga (cashflow)
    i_uzs_target_day = InstallmentPayment.objects.filter(
        Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(
            payment_date__date=target_date_for_daily_stats)).aggregate(paid=Sum('amount', default=Decimal(0)))['paid']
    i_usd_target_day = InstallmentPayment.objects.filter(
        Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.USD) & Q(
            payment_date__date=target_date_for_daily_stats)).aggregate(paid=Sum('amount', default=Decimal(0)))['paid']

    results['today_cashflow_uzs'] = (s_uzs_target_day or Decimal(0)) + (i_uzs_target_day or Decimal(0))
    results['today_sales_uzs_count'] = daily_sales_uzs_c
    results['today_cashflow_usd'] = (s_usd_target_day or Decimal(0)) + (i_usd_target_day or Decimal(0))
    results['today_sales_usd_count'] = daily_sales_usd_c
    results['today_total_sales_count'] = daily_sales_uzs_c + daily_sales_usd_c

    # Sof foyda (target_date uchun)
    daily_sales_profit_qs = Sale.objects.filter(
        base_sales_filter_for_profit & kassa_q_filter_sale & Q(created_at__date=target_date_for_daily_stats))
    daily_net_profit_uzs, daily_net_profit_usd = calculate_net_profit_for_sales(daily_sales_profit_qs)
    results['today_net_profit_uzs'] = daily_net_profit_uzs
    results['today_net_profit_usd'] = daily_net_profit_usd

    # --- "Oylik" (target_month uchun) Statistikalar ---
    # Kassaga tushgan pul (target_month uchun)
    s_uzs_target_month = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
            created_at__date__gte=start_of_target_month) & Q(created_at__date__lte=end_of_target_month)).aggregate(
        paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid']
    monthly_sales_uzs_c = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.UZS) & Q(
            created_at__date__gte=start_of_target_month) & Q(created_at__date__lte=end_of_target_month)).count()
    s_usd_target_month = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.USD) & Q(
            created_at__date__gte=start_of_target_month) & Q(created_at__date__lte=end_of_target_month)).aggregate(
        paid=Sum('amount_actually_paid_at_sale', default=Decimal(0)))['paid']
    monthly_sales_usd_c = Sale.objects.filter(
        base_sales_filter & kassa_q_filter_sale & Q(currency=Sale.SaleCurrency.USD) & Q(
            created_at__date__gte=start_of_target_month) & Q(created_at__date__lte=end_of_target_month)).count()
    i_uzs_target_month = InstallmentPayment.objects.filter(
        Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.UZS) & Q(
            payment_date__date__gte=start_of_target_month) & Q(payment_date__date__lte=end_of_target_month)).aggregate(
        paid=Sum('amount', default=Decimal(0)))['paid']
    i_usd_target_month = InstallmentPayment.objects.filter(
        Q(plan__sale__kassa_id=kassa_id if kassa_id else Q()) & Q(plan__currency=Sale.SaleCurrency.USD) & Q(
            payment_date__date__gte=start_of_target_month) & Q(payment_date__date__lte=end_of_target_month)).aggregate(
        paid=Sum('amount', default=Decimal(0)))['paid']

    results['monthly_cashflow_uzs'] = (s_uzs_target_month or Decimal(0)) + (i_uzs_target_month or Decimal(0))
    results['monthly_sales_uzs_count'] = monthly_sales_uzs_c
    results['monthly_cashflow_usd'] = (s_usd_target_month or Decimal(0)) + (i_usd_target_month or Decimal(0))
    results['monthly_sales_usd_count'] = monthly_sales_usd_c
    results['monthly_total_sales_count'] = monthly_sales_uzs_c + monthly_sales_usd_c

    # Sof foyda (target_month uchun)
    monthly_sales_profit_qs = Sale.objects.filter(
        base_sales_filter_for_profit & kassa_q_filter_sale & Q(created_at__date__gte=start_of_target_month) & Q(
            created_at__date__lte=end_of_target_month))
    monthly_net_profit_uzs, monthly_net_profit_usd = calculate_net_profit_for_sales(monthly_sales_profit_qs)
    results['monthly_net_profit_uzs'] = monthly_net_profit_uzs
    results['monthly_net_profit_usd'] = monthly_net_profit_usd

    # --- Kassa Balanslari (o'zgarishsiz, joriy holatni ko'rsatadi) ---
    if kassa_id:
        results['kassa_balance_uzs'] = get_kassa_balance_currency(kassa_id, Sale.SaleCurrency.UZS)
        results['kassa_balance_usd'] = get_kassa_balance_currency(kassa_id, Sale.SaleCurrency.USD)
        try:
            results['kassa_name'] = Kassa.objects.get(pk=kassa_id).name
        except Kassa.DoesNotExist:
            results['kassa_name'] = None
    else:
        results['kassa_balance_uzs'] = None;
        results['kassa_balance_usd'] = None;
        results['kassa_name'] = "Umumiy"

    # --- Umumiy statistikalar (faqat period_type='all' va target_date/month berilmaganda) ---
    # Yoki bularni har doim qaytarish mumkin. Hozircha, agar aniq sana/oy so'ralsa, bularni qaytarmaymiz.
    if period_type == 'all' and not target_date_str and not target_month_str:
        results['total_products'] = Product.objects.filter(is_active=True).count()
        accessory_categories = Category.objects.filter(is_accessory_category=True)
        results['low_stock_products'] = ProductStock.objects.filter(quantity__lte=F('minimum_stock_level'),
                                                                    product__category__in=accessory_categories).count()
        results['total_customers'] = Customer.objects.count()
        results['new_customers_today'] = Customer.objects.filter(
            created_at__date=current_day_for_calc).count()  # Joriy kun uchun
        # top_products_chart ham joriy oy uchun qolishi mumkin

    results['target_date_processed'] = target_date_for_daily_stats.isoformat()
    results['target_month_processed'] = start_of_target_month.strftime("%Y-%m")

    return results


def get_sales_report_data(period_type='daily', start_date_str=None, end_date_str=None,
                          currency='UZS', seller_id=None, kassa_id=None,
                          payment_type=None, group_by=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {currency}. Mumkin bo'lganlar: {Sale.SaleCurrency.labels}")

    filters = Q(currency=currency) & Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if seller_id: filters &= Q(seller_id=seller_id)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if payment_type: filters &= Q(payment_type=payment_type)

    sales_qs = Sale.objects.filter(filters)

    # "Foyda" ni hisoblash (kassaga tushgan pul)
    total_profit_in_currency = sales_qs.aggregate(
        total_profit=Sum('amount_actually_paid_at_sale', default=Decimal(0))
    )['total_profit'] or Decimal(0)

    chart_data, details = [], []
    trunc_func, date_format = None, None
    if group_by == 'day':
        trunc_func, date_format = TruncDay, '%Y-%m-%d'
    elif group_by == 'week':
        trunc_func, date_format = TruncWeek, '%Y / W%W'
    elif group_by == 'month':
        trunc_func, date_format = TruncMonth, '%Y-%m'

    if trunc_func:
        chart_data_query = sales_qs.annotate(period=trunc_func('created_at')).values('period') \
            .annotate(period_profit=Sum('amount_actually_paid_at_sale', default=Decimal(0))).order_by('period')
        chart_data = [
            {'period': item['period'].strftime(date_format), 'total_profit': item.get('period_profit') or Decimal(0)}
            for item in chart_data_query]

    details_query = sales_qs.select_related('seller', 'customer', 'kassa').annotate(items_count=Count('items')) \
        .values('id', 'created_at', 'seller__username', 'customer__full_name',
                'kassa__name', 'payment_type',
                'original_total_amount_currency',  # Asl summa
                'final_amount_currency',  # Chegirma bilan summa
                'amount_actually_paid_at_sale',  # Haqiqatda to'langan
                'currency', 'items_count').order_by('-created_at')
    details = []
    for item in details_query:
        detail_item = item.copy()
        detail_item['created_at'] = item['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        details.append(detail_item)

    return {'total_profit': total_profit_in_currency, 'currency': currency, 'details': details,
            'chart_data': chart_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Mahsulotlar Hisoboti (Narx `price_at_sale_currency` dan, bu yakuniy narx) ---
def get_products_report_data(period_type='monthly', start_date_str=None, end_date_str=None,
                             currency='UZS', category_id=None):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values: raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(sale__currency=currency) & Q(
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    if start_date: filters &= Q(sale__created_at__date__gte=start_date)
    if end_date: filters &= Q(sale__created_at__date__lte=end_date)
    if category_id: filters &= Q(product__category_id=category_id)

    sale_items_qs = SaleItem.objects.filter(filters).select_related('product', 'product__category', 'sale')

    # Bu yerda SaleItem.price_at_sale_currency ni ishlatamiz, chunki u chegirma qilingan narx
    product_summary = sale_items_qs.values('product_id', 'product__name', 'product__category__name') \
        .annotate(total_quantity=Sum('quantity', default=0),
                  total_sold_amount=Sum(F('quantity') * F('price_at_sale_currency'),
                                        output_field=DecimalField(decimal_places=2), default=Decimal(0))) \
        .order_by('-total_sold_amount')  # Yakuniy sotilgan summa bo'yicha

    grand_total_sold_amount = product_summary.aggregate(grand_total=Sum('total_sold_amount', default=Decimal(0))).get(
        'grand_total') or Decimal(0)
    pie_chart_data = []
    if grand_total_sold_amount > 0:
        pie_chart_data = [{'product_name': p['product__name'],
                           'percentage': float(
                               round((p['total_sold_amount'] / grand_total_sold_amount) * 100, 2)) if p.get(
                               'total_sold_amount') else 0.0
                           } for p in product_summary if p.get('total_sold_amount')]
    return {'currency': currency, 'table_data': list(product_summary), 'pie_chart_data': pie_chart_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Sotuvchilar Hisoboti (Foyda `amount_actually_paid_at_sale` dan) ---
def get_sellers_report_data(period_type='monthly', start_date_str=None, end_date_str=None,
                            currency='UZS'):
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    if currency not in Sale.SaleCurrency.values: raise ValueError(f"Noto'g'ri valyuta: {currency}.")

    filters = Q(currency=currency) & Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & Q(
        seller__isnull=False)
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)

    sales_qs = Sale.objects.filter(filters).select_related('seller', 'seller__profile')

    seller_summary_qs = sales_qs.values('seller_id', 'seller__username', 'seller__profile__full_name') \
        .annotate(total_profit_by_seller=Sum('amount_actually_paid_at_sale', default=Decimal(0)),
                  total_sales_count=Count('id', default=0)).order_by('-total_profit_by_seller')

    report_list = []
    for summary in seller_summary_qs:
        seller_id = summary['seller_id']
        # Sotilgan mahsulotlar soni (shu sotuvchi, davr, valyuta)
        items_sold_count_agg = SaleItem.objects.filter(
            sale__seller_id=seller_id, sale__currency=currency,
            sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED],
            sale__created_at__date__gte=(start_date if start_date else date.min),
            sale__created_at__date__lte=(end_date if end_date else date.max)
        ).aggregate(total_items=Sum('quantity', default=0))
        items_sold_count = items_sold_count_agg.get('total_items') or 0

        report_list.append({
            'seller_id': seller_id, 'username': summary['seller__username'],
            'full_name': summary['seller__profile__full_name'],
            'total_profit_by_seller': summary.get('total_profit_by_seller') or Decimal(0),
            'total_sales_count': summary.get('total_sales_count') or 0,
            'total_items_sold': items_sold_count
        })
    return {'currency': currency, 'table_data': report_list,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


# --- Nasiyalar Hisoboti (O'zgarishsiz qolishi mumkin, chunki u o'z valyutasida) ---
def get_installments_report_data(period_type='all_time', start_date_str=None, end_date_str=None,
                                 customer_id=None, status=None, currency_filter=None):
    # ... (Bu funksiya avvalgi javobdagi kabi to'liq va o'zgarishsiz qoladi) ...
    # Faqat SaleCurrency ni to'g'ri import qilish kerak.
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    filters = Q()
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if customer_id:
        try:
            filters &= Q(customer_id=int(customer_id))
        except ValueError:
            raise ValueError(f"Noto'g'ri customer_id formati: {customer_id}")
    if status:
        if status not in InstallmentPlan.PlanStatus.values: raise ValueError(f"Noto'g'ri nasiya holati: {status}")
        filters &= Q(status=status)
    if currency_filter and currency_filter in Sale.SaleCurrency.values: filters &= Q(currency=currency_filter)
    plans_qs = InstallmentPlan.objects.filter(filters).select_related('customer', 'sale')
    remaining_expression = Cast(F('total_amount_due') - F('return_adjustment') - F('amount_paid'),
                                output_field=DecimalField(decimal_places=2))
    report_values = plans_qs.annotate(remaining_final=remaining_expression) \
        .values('id', 'sale_id', 'currency', 'customer__full_name', 'customer__phone_number',
                'initial_amount', 'interest_rate', 'term_months', 'monthly_payment',
                'total_amount_due', 'down_payment', 'amount_paid', 'remaining_final',
                'status', 'created_at').order_by('-created_at')
    report_list = []
    for plan_data in report_values:
        try:
            plan_instance = InstallmentPlan.objects.prefetch_related('schedule').get(pk=plan_data['id'])
            next_due_date = plan_instance.get_next_payment_due_date
            is_overdue_val = plan_instance.is_overdue()
        except InstallmentPlan.DoesNotExist:
            next_due_date, is_overdue_val = None, False
        report_list.append({
            **plan_data,
            'next_payment_due_date': next_due_date.strftime('%Y-%m-%d') if next_due_date else None,
            'is_overdue': is_overdue_val,
            'status_display': InstallmentPlan.PlanStatus(plan_data.get('status')).label if plan_data.get(
                'status') else None,
            'created_at': plan_data['created_at'].strftime('%Y-%m-%d %H:%M:%S') if plan_data.get(
                'created_at') else None,
            'remaining_amount': plan_data.get('remaining_final') or Decimal(0)
        })
    return {'data': report_list,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'period_type': period_type}


# --- Ombor Hisobotlari (O'zgarishsiz) ---
def get_inventory_stock_report(kassa_id=None, category_id=None, low_stock_only=False):
    # ... (avvalgi kod) ...
    filters = Q()
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if category_id: filters &= Q(product__category_id=category_id)
    if low_stock_only: filters &= Q(quantity__lte=F('minimum_stock_level'))
    stocks = ProductStock.objects.filter(filters).select_related('product__category', 'kassa', 'product').order_by(
        'kassa__name', 'product__name')
    report_data = []
    for stock in stocks:
        report_data.append({
            'product_id': stock.product_id, 'product_name': stock.product.name, 'barcode': stock.product.barcode,
            'category_name': stock.product.category.name if stock.product.category else None,
            'kassa_id': stock.kassa_id, 'kassa_name': stock.kassa.name,
            'quantity': stock.quantity, 'minimum_stock_level': stock.minimum_stock_level,
            'is_low_stock': stock.is_low_stock, 'price_uzs': stock.product.price_uzs,
            'price_usd': stock.product.price_usd,
        })
    return report_data


def get_inventory_history_report(period_type='daily', start_date_str=None, end_date_str=None, kassa_id=None,
                                 product_id=None, user_id=None, operation_type=None):
    # ... (avvalgi kod) ...
    start_date, end_date = get_date_range_from_period(period_type, start_date_str, end_date_str)
    filters = Q()
    if start_date: filters &= Q(timestamp__date__gte=start_date)
    if end_date: filters &= Q(timestamp__date__lte=end_date)
    if kassa_id: filters &= Q(kassa_id=kassa_id)
    if product_id: filters &= Q(product_id=product_id)
    if user_id: filters &= Q(user_id=user_id)
    if operation_type: filters &= Q(operation_type=operation_type)
    operations = InventoryOperation.objects.filter(filters).select_related('product', 'kassa',
                                                                           'user__profile').order_by('-timestamp')
    report_data = []
    for op in operations:
        report_data.append({
            'id': op.id, 'timestamp': op.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'product_name': op.product.name, 'kassa_name': op.kassa.name, 'quantity': op.quantity,
            'operation_type': op.operation_type, 'operation_type_display': op.get_operation_type_display(),
            'user_username': op.user.username if op.user else None,
            'user_full_name': op.user.profile.full_name if op.user and hasattr(op.user, 'profile') else None,
            'comment': op.comment,
        })
    return {'data': report_data,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None}


def get_sales_chart_data(period_type='monthly', currency='UZS', kassa_id=None, start_date_str=None, end_date_str=None):
    target_currency = currency.upper()
    if target_currency not in Sale.SaleCurrency.values:
        raise ValueError(f"Noto'g'ri valyuta: {target_currency}.")

    period_type_internal = period_type.lower()  # group_by uchun ishlatiladi

    # Sana oralig'ini aniqlash
    if start_date_str and end_date_str:
        try:
            date_range_start = date.fromisoformat(start_date_str)
            date_range_end = date.fromisoformat(end_date_str)
            if date_range_start > date_range_end:
                raise ValueError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
        except ValueError:
            raise ValueError("Noto'g'ri sana formati (start_date/end_date). YYYY-MM-DD bo'lishi kerak.")
    elif start_date_str:  # Faqat boshlanish sanasi berilsa, o'sha kunni olamiz
        try:
            date_range_start = date_range_end = date.fromisoformat(start_date_str)
        except ValueError:
            raise ValueError("Noto'g'ri sana formati (start_date). YYYY-MM-DD bo'lishi kerak.")
    else:  # Agar sana oralig'i berilmasa, period_type ga qarab standart oralig'ni olamiz
        today = timezone.now().date()
        if period_type_internal == 'daily':  # Oxirgi 7 kun
            date_range_end = today
            date_range_start = today - timedelta(days=6)
        elif period_type_internal == 'weekly':  # Oxirgi 4 hafta
            date_range_end = today
            # Haftaning birinchi kunidan boshlab hisoblash uchun
            current_week_start_for_calc = today - timedelta(days=today.weekday())
            date_range_start = current_week_start_for_calc - timedelta(weeks=3)
        elif period_type_internal == 'monthly':  # Joriy oyning kunlari (yoki oxirgi 30 kun)
            # Hozirgi oyning kunlari
            date_range_start = today.replace(day=1)
            _, last_day_of_month = calendar.monthrange(today.year, today.month)
            date_range_end = today.replace(day=last_day_of_month)
        else:
            raise ValueError(
                f"Noto'g'ri 'period_type' (agar sana berilmagan bo'lsa): {period_type}. Mumkin: 'daily', 'weekly', 'monthly'.")

    # Guruhlash funksiyasi va label formati
    group_by_func = None
    label_format = ""
    all_labels_in_period = []

    # period_type_internal endi guruhlash intervalini bildiradi
    if period_type_internal == 'daily':  # Kunlar bo'yicha guruhlash
        group_by_func = TruncDay
        label_format = '%Y-%m-%d'
        current_day = date_range_start
        while current_day <= date_range_end:
            all_labels_in_period.append(current_day.strftime(label_format))
            current_day += timedelta(days=1)
    elif period_type_internal == 'weekly':  # Haftalar bo'yicha guruhlash
        group_by_func = TruncWeek
        label_format = '%Y / W%W'  # Yil / Hafta raqami
        current_week_start_for_label = date_range_start - timedelta(days=date_range_start.weekday())
        while current_week_start_for_label <= date_range_end:
            all_labels_in_period.append(current_week_start_for_label.strftime(label_format))
            # Keyingi haftaga o'tishda ehtiyot bo'lish kerak, agar date_range_end haftaning o'rtasida bo'lsa
            if current_week_start_for_label + timedelta(
                    weeks=1) > date_range_end and current_week_start_for_label < date_range_end:
                # Agar oxirgi hafta to'liq bo'lmasa ham label qo'shish (ixtiyoriy)
                if (date_range_end - timedelta(days=date_range_end.weekday())).strftime(
                        label_format) not in all_labels_in_period:
                    all_labels_in_period.append(
                        (date_range_end - timedelta(days=date_range_end.weekday())).strftime(label_format))
                break
            current_week_start_for_label += timedelta(weeks=1)
            if len(all_labels_in_period) > 100: break  # Cheksiz tsiklni oldini olish

    elif period_type_internal == 'monthly':  # Oylar bo'yicha guruhlash
        group_by_func = TruncMonth
        label_format = '%Y-%m'
        current_month_start_for_label = date_range_start.replace(day=1)
        while current_month_start_for_label <= date_range_end:
            all_labels_in_period.append(current_month_start_for_label.strftime(label_format))
            # Keyingi oyga o'tish
            next_month_year = current_month_start_for_label.year
            next_month_month = current_month_start_for_label.month + 1
            if next_month_month > 12:
                next_month_month = 1
                next_month_year += 1
            if date(next_month_year, next_month_month, 1) > date_range_end.replace(
                    day=1) and current_month_start_for_label.strftime(label_format) != date_range_end.replace(
                    day=1).strftime(label_format):
                if date_range_end.replace(day=1).strftime(label_format) not in all_labels_in_period:
                    all_labels_in_period.append(date_range_end.replace(day=1).strftime(label_format))
                break
            current_month_start_for_label = date(next_month_year, next_month_month, 1)
            if len(all_labels_in_period) > 100: break  # Cheksiz tsiklni oldini olish
    else:
        raise ValueError(f"Noto'g'ri guruhlash 'period_type': {period_type_internal}.")

    # Filtrlar
    base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & \
                        Q(currency=target_currency) & \
                        Q(created_at__date__gte=date_range_start) & Q(created_at__date__lte=date_range_end)
    base_installments_filter = Q(plan__currency=target_currency) & \
                               Q(payment_date__date__gte=date_range_start) & Q(payment_date__date__lte=date_range_end)
    if kassa_id:
        base_sales_filter &= Q(kassa_id=kassa_id)
        base_installments_filter &= Q(plan__sale__kassa_id=kassa_id)

    # Ma'lumotlarni olish
    sales_data_qs = Sale.objects.filter(base_sales_filter) \
        .annotate(period_group=group_by_func('created_at')) \
        .values('period_group') \
        .annotate(total=Sum(Coalesce('amount_actually_paid_at_sale', Value(0)), output_field=DecimalField())) \
        .order_by('period_group')

    installments_data_qs = InstallmentPayment.objects.filter(base_installments_filter) \
        .annotate(period_group=group_by_func('payment_date')) \
        .values('period_group') \
        .annotate(total=Sum(Coalesce('amount', Value(0)), output_field=DecimalField())) \
        .order_by('period_group')

    aggregated_data = {}
    for item in sales_data_qs:
        if item['period_group']:
            period_label = item['period_group'].strftime(label_format)
            aggregated_data[period_label] = aggregated_data.get(period_label, Decimal(0)) + (
                        item['total'] or Decimal(0))
    for item in installments_data_qs:
        if item['period_group']:
            period_label = item['period_group'].strftime(label_format)
            aggregated_data[period_label] = aggregated_data.get(period_label, Decimal(0)) + (
                        item['total'] or Decimal(0))

    chart_labels = all_labels_in_period
    chart_values = [aggregated_data.get(label, Decimal(0)) for label in chart_labels]

    # Agar all_labels_in_period bo'sh bo'lsa (masalan, juda qisqa davr va 'monthly' guruhlash)
    if not chart_labels and (
            sales_data_qs.exists() or installments_data_qs.exists()):  # Agar ma'lumot boru, label yo'q bo'lsa
        # Barcha ma'lumotni bitta labelga jamlash (davrning boshlanish sanasi bilan)
        total_sum_for_empty_labels = sum(chart_values)  # chart_values bu holatda bo'sh bo'ladi
        total_sum_for_empty_labels = sum(aggregated_data.values())

        if total_sum_for_empty_labels > 0:  # Faqat agar summa bo'lsa
            chart_labels = [date_range_start.strftime(
                label_format if label_format else '%Y-%m-%d')]  # Boshlanish sanasini label qilish
            chart_values = [total_sum_for_empty_labels]

    return {
        "currency": target_currency, "requested_period_type": period_type,
        "grouping_interval": period_type_internal,  # Qanday intervalda guruhlanganini ko'rsatish
        "date_range_start": date_range_start.isoformat(), "date_range_end": date_range_end.isoformat(),
        "labels": chart_labels, "data": chart_values,
    }
# YANGI FUNKSIYA: Sotuvlar grafigi uchun ma'lumotlarni tayyorlash
# def get_sales_chart_data(period_type='monthly', currency='UZS', kassa_id=None):
#     """
#     Sotuvlar grafigi uchun ma'lumotlarni tayyorlaydi.
#     'period_type' (daily, weekly, monthly) va 'currency' (UZS, USD) bo'yicha.
#     Natijada 'labels' va 'data' massivlarini qaytaradi.
#     """
#     today = timezone.now().date()
#     target_currency = currency.upper()
#     if target_currency not in Sale.SaleCurrency.values:
#         raise ValueError(f"Noto'g'ri valyuta: {target_currency}. Mumkin: {Sale.SaleCurrency.labels}")
#
#     period_type = period_type.lower()
#     group_by_func = None
#     label_format = ""
#     date_range_start, date_range_end = None, None
#     all_labels_in_period = []  # Barcha mumkin bo'lgan labellarni saqlash uchun
#
#     base_sales_filter = Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & \
#                         Q(currency=target_currency)
#     base_installments_filter = Q(plan__currency=target_currency)  # Nasiya to'lovlari uchun
#
#     if kassa_id:
#         try:
#             kassa_id = int(kassa_id)
#             base_sales_filter &= Q(kassa_id=kassa_id)
#             base_installments_filter &= Q(plan__sale__kassa_id=kassa_id)
#         except ValueError:
#             raise ValueError("Noto'g'ri kassa_id formati.")
#
#     if period_type == 'daily':  # Joriy kun (hozircha faqat bitta nuqta qaytaradi, ko'p kunlik uchun 'weekly' yoki 'monthly' yaxshiroq)
#         # Yoki o'tgan X kun uchun qilish mumkin. Hozircha soddalik uchun joriy kun.
#         # Agar 'daily' o'tgan 7 kunni anglatsa, logikani o'zgartirish kerak.
#         # Keling, 'daily' ni o'tgan 7 kun deb qabul qilaylik, grafik uchun qulayroq.
#         date_range_end = today
#         date_range_start = today - timedelta(days=6)
#         group_by_func = TruncDay
#         label_format = '%Y-%m-%d'
#         current_day = date_range_start
#         while current_day <= date_range_end:
#             all_labels_in_period.append(current_day.strftime(label_format))
#             current_day += timedelta(days=1)
#
#     elif period_type == 'weekly':  # Joriy hafta (kunlar bo'yicha)
#         # Yoki o'tgan 4 hafta? Hozircha joriy haftaning kunlari.
#         # Keling, o'tgan 4 haftani olaylik (har bir hafta bitta nuqta)
#         date_range_end = today
#         date_range_start = today - timedelta(weeks=3)  # Joriy hafta + oldingi 3 hafta
#         group_by_func = TruncWeek  # Haftalar bo'yicha guruhlaymiz
#         label_format = '%Y / W%W'  # Yil / Hafta raqami
#
#         current_week_start = date_range_start - timedelta(days=date_range_start.weekday())
#         while current_week_start <= date_range_end:
#             all_labels_in_period.append(current_week_start.strftime(label_format))
#             current_week_start += timedelta(weeks=1)
#
#
#     elif period_type == 'monthly':  # Joriy oy (kunlar bo'yicha)
#         # Yoki o'tgan X oy? Hozircha joriy oyning kunlari.
#         # Keling, joriy oyning kunlarini olaylik
#         date_range_start = today.replace(day=1)
#         _, last_day_of_month = calendar.monthrange(today.year, today.month)
#         date_range_end = today.replace(day=last_day_of_month)
#         group_by_func = TruncDay  # Kunlar bo'yicha guruhlaymiz
#         label_format = '%Y-%m-%d'
#         current_day = date_range_start
#         while current_day <= date_range_end:
#             all_labels_in_period.append(current_day.strftime(label_format))
#             current_day += timedelta(days=1)
#
#     else:
#         raise ValueError(f"Noto'g'ri 'period_type': {period_type}. Mumkin: 'daily', 'weekly', 'monthly'.")
#
#     # Sotuvlardan tushgan pul
#     sales_data = Sale.objects.filter(
#         base_sales_filter & Q(created_at__date__gte=date_range_start) & Q(created_at__date__lte=date_range_end)) \
#         .annotate(period_group=group_by_func('created_at')) \
#         .values('period_group') \
#         .annotate(total=Sum('amount_actually_paid_at_sale', default=Decimal(0))) \
#         .order_by('period_group')
#
#     # Nasiyalardan tushgan pul
#     installments_data = InstallmentPayment.objects.filter(
#         base_installments_filter & Q(payment_date__date__gte=date_range_start) & Q(
#             payment_date__date__lte=date_range_end)) \
#         .annotate(period_group=group_by_func('payment_date')) \
#         .values('period_group') \
#         .annotate(total=Sum('amount', default=Decimal(0))) \
#         .order_by('period_group')
#
#     # Natijalarni birlashtirish
#     aggregated_data = {}  # {'2023-05-01': Decimal('100.00'), ...}
#
#     for item in sales_data:
#         if item['period_group']:  # None bo'lmasligi kerak
#             period_label = item['period_group'].strftime(label_format)
#             aggregated_data[period_label] = aggregated_data.get(period_label, Decimal(0)) + (
#                         item['total'] or Decimal(0))
#
#     for item in installments_data:
#         if item['period_group']:
#             period_label = item['period_group'].strftime(label_format)
#             aggregated_data[period_label] = aggregated_data.get(period_label, Decimal(0)) + (
#                         item['total'] or Decimal(0))
#
#     # Grafik uchun 'labels' va 'data' tayyorlash
#     # all_labels_in_period bo'yicha yurib, aggregated_data dan qiymat olish
#     chart_labels = all_labels_in_period
#     chart_values = [aggregated_data.get(label, Decimal(0)) for label in chart_labels]
#
#     return {
#         "currency": target_currency,
#         "period_type": period_type,
#         "period_label_format": label_format,
#         "labels": chart_labels,
#         "data": chart_values,
#         "debug_date_range_start": date_range_start.isoformat() if date_range_start else None,
#         "debug_date_range_end": date_range_end.isoformat() if date_range_end else None,
#     }