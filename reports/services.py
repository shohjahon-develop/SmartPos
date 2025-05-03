# reports/services.py
from django.db.models import Sum, Count, F, DecimalField, Q, Value,Case, When
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, Cast
from django.utils import timezone
from datetime import timedelta, datetime, date # date ni import qilish
from decimal import Decimal # Decimalni import qilish

# --- Importlar qisqartirildi ---
from sales.models import Sale, SaleItem, Customer, KassaTransaction
from products.models import Product, Category, Kassa
from users.models import User # Yoki settings.AUTH_USER_MODEL
from inventory.models import ProductStock
from installments.models import InstallmentPlan
# --- Eksport bilan bog'liq importlar olib tashlandi ---

# --- Dashboard uchun statistika ---
def get_kassa_balance(kassa_id):
    """Belgilangan kassa uchun joriy balansni hisoblaydi"""
    try:
        # Kassa mavjudligini tekshirish
        kassa = Kassa.objects.get(pk=kassa_id)
        # Kirim turlari
        income_types = [
            KassaTransaction.TransactionType.SALE,
            KassaTransaction.TransactionType.INSTALLMENT_PAYMENT,
            KassaTransaction.TransactionType.CASH_IN,
        ]
        # Chiqim turlari
        expense_types = [
            KassaTransaction.TransactionType.CASH_OUT,
            KassaTransaction.TransactionType.RETURN_REFUND,
        ]

        balance_agg = KassaTransaction.objects.filter(kassa=kassa).aggregate(
            total_income=Sum(
                Case(When(transaction_type__in=income_types, then=F('amount')), default=Value(Decimal(0))),
                output_field=DecimalField(decimal_places=2)
            ),
            total_expense=Sum(
                 Case(When(transaction_type__in=expense_types, then=F('amount')), default=Value(Decimal(0))),
                 output_field=DecimalField(decimal_places=2)
            )
        )
        # Agar aggregate natijalari None bo'lsa, 0 ga o'tkazamiz
        income = balance_agg.get('total_income') or Decimal(0)
        expense = balance_agg.get('total_expense') or Decimal(0)
        return income - expense
    except Kassa.DoesNotExist:
        print(f"Warning: Kassa with id={kassa_id} not found for balance calculation.")
        return Decimal(0)
    except Exception as e:
         print(f"Error calculating kassa balance for {kassa_id}: {e}")
         return None

# --- Dashboard uchun statistika (store_id bo'yicha) ---
def get_dashboard_stats(store_id, kassa_id=None):
    """Dashboard statistikasini berilgan do'kon va (ixtiyoriy) kassa bo'yicha hisoblaydi"""
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    # start_of_week = today - timedelta(days=today.weekday()) # Bu kerak emas hozircha

    # Asosiy filtrlar (Do'kon bo'yicha)
    base_sales_filter = Q(store_id=store_id, status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])
    base_product_filter = Q(store_id=store_id)
    # ProductStock product orqali store ga bog'liq
    base_stock_filter = Q(product__store_id=store_id)
    base_customer_filter = Q(store_id=store_id)

    # Kunlik sotuvlar
    today_sales_agg = Sale.objects.filter(base_sales_filter & Q(created_at__date=today)) \
                       .aggregate(total_uzs=Sum('total_amount_uzs', default=Decimal(0)),
                                  count=Count('id', default=0))

    # Oylik sotuvlar
    monthly_sales_agg = Sale.objects.filter(base_sales_filter & Q(created_at__date__gte=start_of_month)) \
                         .aggregate(total_uzs=Sum('total_amount_uzs', default=Decimal(0)),
                                    count=Count('id', default=0))

    # Mahsulotlar soni (aktiv)
    product_count = Product.objects.filter(base_product_filter & Q(is_active=True)).count()

    # Kam qoldiqdagi mahsulotlar soni
    low_stock_count = ProductStock.objects.filter(base_stock_filter & Q(quantity__lte=F('minimum_stock_level'))).count()

    # Mijozlar soni
    customer_count = Customer.objects.filter(base_customer_filter).count()

    # Bugun qo'shilgan mijozlar
    new_customers_today = Customer.objects.filter(base_customer_filter & Q(created_at__date=today)).count()

    # Haftalik sotuvlar grafigi (oxirgi 7 kun)
    weekly_sales_data = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        daily_sales = Sale.objects.filter(base_sales_filter & Q(created_at__date=day)) \
                           .aggregate(daily_total=Sum('total_amount_uzs', default=Decimal(0)))
        weekly_sales_data.append({'day': day.strftime('%Y-%m-%d'),
                                  'daily_total': daily_sales.get('daily_total') or Decimal(0)})

    # Top mahsulotlar (oxirgi 30 kun)
    thirty_days_ago = today - timedelta(days=30)
    top_products = SaleItem.objects.filter(
            sale__store_id=store_id, # Do'kon bo'yicha filtr
            sale__created_at__date__gte=thirty_days_ago,
            sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
        ).values('product__name') \
        .annotate(total_quantity_sold=Sum('quantity')) \
        .order_by('-total_quantity_sold')[:5] # Top 5 ta

    # Kassa balansi (agar kassa ID berilgan bo'lsa)
    current_kassa_balance = None
    kassa_name = None
    if kassa_id:
         current_kassa_balance = get_kassa_balance(kassa_id) # Yuqoridagi funksiya
         try:
             # Kassa nomi uchun bazaga murojaat (do'konga tegishli ekanligini tekshirish shart emas,
             # chunki get_kassa_balance xato qaytarmagan bo'lsa, kassa mavjud)
             kassa = Kassa.objects.values('name').get(pk=kassa_id)
             kassa_name = kassa['name']
         except Kassa.DoesNotExist:
             kassa_name = "Noma'lum Kassa"

    return {
        'today_sales_uzs': today_sales_agg.get('total_uzs'),
        'today_sales_count': today_sales_agg.get('count'),
        'monthly_sales_uzs': monthly_sales_agg.get('total_uzs'),
        'monthly_sales_count': monthly_sales_agg.get('count'),
        'total_products': product_count,
        'low_stock_products': low_stock_count,
        'total_customers': customer_count,
        'new_customers_today': new_customers_today,
        'kassa_balance': current_kassa_balance,
        'kassa_name': kassa_name,
        'weekly_sales_chart': weekly_sales_data,
        'top_products_chart': list(top_products),
    }

# --- Sotuvlar Hisoboti (store_id bo'yicha) ---
def get_sales_report_data(store_id, start_date, end_date, currency='UZS', seller_id=None, kassa_id=None, payment_type=None, group_by=None):
    """Sotuvlar hisobotini berilgan do'kon va filterlar bo'yicha qaytaradi"""

    # Asosiy filter (do'kon, sana, status)
    filters = Q(store_id=store_id) & \
              Q(created_at__date__gte=start_date) & \
              Q(created_at__date__lte=end_date) & \
              Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    # Qo'shimcha filterlar
    if seller_id:
        # Sotuvchi shu do'kondami? (qo'shimcha tekshirish mumkin)
        # if not UserProfile.objects.filter(user_id=seller_id, store_id=store_id).exists():
        #     raise ValueError(f"Seller with ID {seller_id} not found in store {store_id}")
        filters &= Q(seller_id=seller_id)
    if kassa_id:
        # Kassa shu do'kondami? (qo'shimcha tekshirish mumkin)
        # if not Kassa.objects.filter(id=kassa_id, store_id=store_id).exists():
        #     raise ValueError(f"Kassa with ID {kassa_id} not found in store {store_id}")
        filters &= Q(kassa_id=kassa_id)
    if payment_type:
        # To'lov turi validatsiyasi (agar kerak bo'lsa)
        if payment_type not in Sale.PaymentType.values:
             raise ValueError(f"Invalid payment type: {payment_type}")
        filters &= Q(payment_type=payment_type)

    # Filterlangan sotuvlar QuerySet'i
    sales_qs = Sale.objects.filter(filters)

    # Summa uchun maydonni aniqlash
    amount_field = 'total_amount_uzs' if currency == 'UZS' else 'total_amount_usd'

    # Umumiy summani hisoblash
    total_sum = sales_qs.aggregate(total=Sum(amount_field, default=Decimal(0)))['total']

    # Grafik va detal ma'lumotlari uchun
    chart_data = []
    details = []

    # Guruhlash logikasi
    if group_by == 'day': trunc_func, date_format = TruncDay, '%Y-%m-%d'
    elif group_by == 'week': trunc_func, date_format = TruncWeek, '%Y / W%W' # Hafta formati
    elif group_by == 'month': trunc_func, date_format = TruncMonth, '%Y-%m'
    else: trunc_func = None

    if trunc_func:
        # Grafik uchun ma'lumotlar (davr bo'yicha guruhlangan)
        chart_data_query = sales_qs.annotate(period=trunc_func('created_at')) \
                                .values('period') \
                                .annotate(period_total=Sum(amount_field, default=Decimal(0))) \
                                .order_by('period')
        # Natijani formatlash
        chart_data = [{'period': item['period'].strftime(date_format),
                       'total': item.get('period_total') or Decimal(0)}
                      for item in chart_data_query]
        # Guruhlanganda detal ma'lumot bo'lmaydi
        details = []
    else:
        # Detal ma'lumotlar (guruhlanmagan)
        details_query = sales_qs.select_related('seller', 'customer', 'kassa') \
                             .annotate(items_count=Count('items')) \
                             .values(
                                 'id', 'created_at', 'seller__username',
                                 'customer__full_name', 'kassa__name', 'payment_type',
                                 amount_field, # Bu yerda to'g'ridan-to'g'ri maydon nomi
                                 'items_count'
                             ).order_by('-created_at') # Oxirgilari birinchi

        # Natijani JSON uchun moslashtirish (masalan, sanani string qilish)
        details = [
            {**item,
             'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
             'total_amount': item.get(amount_field) or Decimal(0)} # Maydon nomini birxillashtirish
            for item in details_query
        ]
        # Guruhlanmaganda grafik ma'lumoti bo'lmaydi
        chart_data = []

    return {'total': total_sum, 'details': details, 'chart_data': chart_data}

# --- Mahsulotlar Hisoboti (store_id bo'yicha) ---
def get_products_report_data(store_id, start_date, end_date, category_id=None, currency='UZS'):
    """Mahsulotlar sotuvi hisobotini berilgan do'kon va filterlar bo'yicha qaytaradi"""

    # Asosiy filter (do'kon, sana, status)
    filters = Q(sale__store_id=store_id) & \
              Q(sale__created_at__date__gte=start_date) & \
              Q(sale__created_at__date__lte=end_date) & \
              Q(sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED])

    # Kategoriya filteri (agar berilgan bo'lsa)
    if category_id:
        # Kategoriya shu do'kongami? (tekshirish mumkin)
        # if not Category.objects.filter(Q(id=category_id, store_id=store_id) | Q(id=category_id, store_id=None)).exists():
        #     raise ValueError(f"Category with ID {category_id} not found in store {store_id} or globally.")
        filters &= Q(product__category_id=category_id)

    # Filterlangan sotuv elementlari
    sale_items_qs = SaleItem.objects.filter(filters).select_related('product', 'product__category') # Bog'liq modellarni olish

    # Narx uchun maydonni aniqlash
    price_field_str = 'price_at_sale_uzs' if currency == 'UZS' else 'price_at_sale_usd'
    price_field_f = F(price_field_str) # F objecti

    # Mahsulotlar bo'yicha jamlanma
    product_summary = sale_items_qs.values(
            'product_id', # ID ni olish yaxshiroq
            'product__name',
            'product__category__name' # Kategoriya nomini ham olish
        ).annotate(
            total_quantity=Sum('quantity', default=0),
            total_amount=Sum(F('quantity') * price_field_f, output_field=DecimalField(decimal_places=2), default=Decimal(0))
        ).order_by('-total_amount') # Eng ko'p sotilganlar birinchi

    # Pie chart uchun umumiy summani hisoblash
    total_sales_amount = product_summary.aggregate(total=Sum('total_amount', default=Decimal(0)))['total']

    # Pie chart ma'lumotlarini tayyorlash
    pie_chart_data = []
    if total_sales_amount and total_sales_amount > 0: # 0 ga bo'lish xatoligini oldini olish
        pie_chart_data = [
            {
                'product_name': p['product__name'],
                # Foizni hisoblash (float ga o'tkazish JSON uchun yaxshi)
                'percentage': float(round((p['total_amount'] / total_sales_amount) * 100, 2)) if p['total_amount'] else 0.0
            } for p in product_summary if p.get('total_amount') # Faqat summasi borlarni qo'shish
        ]
        # Agar mahsulot ko'p bo'lsa, kichik foizlilarni "Boshqalar" ga birlashtirish mumkin

    return {
        'table_data': list(product_summary), # Jadval uchun
        'pie_chart_data': pie_chart_data     # Pie chart uchun
    }

# --- Sotuvchilar Hisoboti (store_id bo'yicha) ---
def get_sellers_report_data(store_id, start_date, end_date, currency='UZS'):
    """Sotuvchilarning sotuv hisobotini berilgan do'kon va sana oralig'ida qaytaradi"""

    # Asosiy filter (do'kon, sana, status, sotuvchi mavjudligi)
    filters = Q(store_id=store_id) & \
              Q(created_at__date__gte=start_date) & \
              Q(created_at__date__lte=end_date) & \
              Q(status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]) & \
              Q(seller__isnull=False) # Sotuvchisi bo'lmaganlarni hisobga olmaslik

    # Filterlangan sotuvlar
    sales_qs = Sale.objects.filter(filters).select_related('seller', 'seller__profile') # Profilni ham olish (ismi uchun)

    # Summa uchun maydon
    amount_field = 'total_amount_uzs' if currency == 'UZS' else 'total_amount_usd'

    # Sotuvchilar bo'yicha jamlanma
    seller_summary = sales_qs.values(
            'seller_id',
            'seller__username',
            'seller__profile__full_name' # Sotuvchining to'liq ismi
        ).annotate(
            total_sales_amount=Sum(amount_field, default=Decimal(0)),
            total_sales_count=Count('id', default=0),
            # Sotilgan mahsulotlar umumiy soni (har bir sotuvdagi itemlar yig'indisi)
            # Bu biroz murakkabroq, SaleItem orqali qilish kerak yoki alohida hisoblash
            # total_items_sold=Sum('items__quantity', default=0) # Bu to'g'ri ishlamasligi mumkin
        ).order_by('-total_sales_amount') # Eng ko'p sotganlar birinchi

    # total_items_sold ni alohida hisoblash (agar kerak bo'lsa)
    seller_ids = [s['seller_id'] for s in seller_summary]
    items_sold_agg = SaleItem.objects.filter(
        sale__store_id=store_id,
        sale__seller_id__in=seller_ids,
        sale__created_at__date__gte=start_date,
        sale__created_at__date__lte=end_date,
        sale__status__in=[Sale.SaleStatus.COMPLETED, Sale.SaleStatus.PARTIALLY_RETURNED]
    ).values('sale__seller_id').annotate(
        total_items=Sum('quantity', default=0)
    )
    items_sold_map = {item['sale__seller_id']: item['total_items'] for item in items_sold_agg}

    # Natijani formatlash
    report_list = []
    for summary in seller_summary:
        seller_id = summary['seller_id']
        report_list.append({
            'seller_id': seller_id,
            'username': summary['seller__username'],
            'full_name': summary['seller__profile__full_name'],
            'total_sales_amount': summary.get('total_sales_amount') or Decimal(0),
            'total_sales_count': summary.get('total_sales_count') or 0,
            'total_items_sold': items_sold_map.get(seller_id, 0) # Hisoblangan qiymatni qo'shish
        })

    return {
        'table_data': report_list,
        # Bu hisobot uchun grafik odatda bo'lmaydi, lekin qo'shish mumkin
    }

# --- Nasiyalar Hisoboti (store_id bo'yicha) ---
def get_installments_report_data(store_id, start_date=None, end_date=None, customer_id=None, status=None):
    """Nasiyalar hisobotini berilgan do'kon va filterlar bo'yicha qaytaradi"""

    # Asosiy filter (do'kon)
    filters = Q(store_id=store_id)

    # Qo'shimcha filterlar
    if start_date: filters &= Q(created_at__date__gte=start_date)
    if end_date: filters &= Q(created_at__date__lte=end_date)
    if customer_id:
        # Mijoz shu do'kondami? (tekshirish mumkin)
        # if not Customer.objects.filter(id=customer_id, store_id=store_id).exists():
        #     raise ValueError(f"Customer with ID {customer_id} not found in store {store_id}")
        filters &= Q(customer_id=customer_id)
    if status:
        if status not in InstallmentPlan.PlanStatus.values:
            raise ValueError(f"Invalid installment status: {status}")
        filters &= Q(status=status)

    # Nasiya rejalari
    plans_qs = InstallmentPlan.objects.filter(filters) \
                  .select_related('customer', 'sale') # Bog'liq modellarni olish

    # Qoldiqni hisoblash uchun Cast va output_field kerak
    remaining_expression = Cast(
        F('total_due') - F('return_adjustment') - F('amount_paid'),
        output_field=DecimalField(decimal_places=2)
    )

    # Kerakli maydonlarni olish va qoldiqni annotate qilish
    report_values = plans_qs.annotate(remaining=remaining_expression) \
                  .values(
                      'id', 'sale_id', # sale__id o'rniga sale_id to'g'riroq
                      'customer__full_name', 'customer__phone_number',
                      'total_due', 'amount_paid', 'return_adjustment', 'remaining',
                      'next_payment_date', 'status', 'created_at'
                  ).order_by('-created_at') # Oxirgilari birinchi

    # Natijani JSON uchun moslashtirish (sanalarni string qilish, None qiymatlarni to'g'rilash)
    report_list = []
    for plan in report_values:
         # get() metodi bilan None qiymatlardan himoyalanish
         report_list.append({
             'id': plan['id'],
             'sale_id': plan.get('sale_id'),
             'customer_full_name': plan.get('customer__full_name'),
             'customer_phone_number': plan.get('customer__phone_number'),
             'total_due': plan.get('total_due') or Decimal(0),
             'amount_paid': plan.get('amount_paid') or Decimal(0),
             'return_adjustment': plan.get('return_adjustment') or Decimal(0),
             'remaining_amount': plan.get('remaining') or Decimal(0), # Nomini o'zgartirdim
             'next_payment_date': plan['next_payment_date'].strftime('%Y-%m-%d') if plan.get('next_payment_date') else None,
             'status': plan.get('status'),
             # status_display ni qo'shish mumkin (modeldagi choices dan)
             'status_display': InstallmentPlan.PlanStatus(plan.get('status')).label if plan.get('status') else None,
             'created_at': plan['created_at'].strftime('%Y-%m-%d %H:%M:%S') if plan.get('created_at') else None,
         })

    return report_list # Endi bu faqat list of dict