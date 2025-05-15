#
# products/services.py
import random
import string

import barcode
from barcode import EAN14  # EAN14 ni import qilamiz
from barcode.writer import ImageWriter  # Bu generate_barcode_image uchun
from io import BytesIO
import base64
from .models import Product, Category


def generate_ean14_content_with_checksum(indicator='1', company_prefix='', item_ref_length=None):
    """
    EAN-14 uchun 13 raqamli KONTENTNI generatsiya qiladi va keyin
    EAN14 klassi yordamida CHECKSUM BILAN 14 raqamli TO'LIQ KODNI qaytaradi.
    Bu funksiya qavslarni qo'shmaydi.
    """
    data_to_encode = str(indicator) + str(company_prefix)

    # Agar item_ref_length berilmagan bo'lsa, 13 gacha to'ldiramiz
    if item_ref_length is None:
        current_length = len(data_to_encode)
        item_ref_length = 13 - current_length

    if item_ref_length < 0:
        raise ValueError("Indikator va kompaniya prefiksi birgalikda 13 raqamdan oshmasligi kerak.")

    random_part = ''.join(random.choices(string.digits, k=item_ref_length))
    barcode_content_13_digits = data_to_encode + random_part

    if len(barcode_content_13_digits) != 13:
        # Bu holat bo'lmasligi kerak, lekin himoya uchun
        raise ValueError(f"Generatsiya qilingan kontent uzunligi 13 emas: {barcode_content_13_digits}")

    try:
        ean14_obj = EAN14(barcode_content_13_digits)  # 13 raqamli qiymatni kutadi
        return ean14_obj.ean  # Bu checksum bilan birga 14 raqamli kod
    except Exception as e:
        raise ValueError(f"EAN14 checksum generatsiyasida xato: {e}, kontent: {barcode_content_13_digits}")


def generate_unique_ean14_for_product(category_id=None, indicator='1'):
    """
    Mahsulot uchun unikal EAN-14 shtrix-kodini (kerak bo'lsa AI qavslar bilan) generatsiya qiladi.
    Qaytariladigan qiymat: "(AI)DATACHECKSUM" yoki "INDICATORDATACHECKSUM"
    """
    cat_prefix_raw = ""  # Qavssiz prefiks
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                cat_prefix_raw = str(category.barcode_prefix).strip()
        except Category.DoesNotExist:
            pass

    while True:
        # EAN-14 uchun 14 raqamli kodni (checksum bilan) olish
        # Bu yerda company_prefix = cat_prefix_raw bo'ladi
        # item_ref_length ni generate_ean14_content_with_checksum o'zi hisoblaydi

        full_14_digit_code = generate_ean14_content_with_checksum(
            indicator=indicator,
            company_prefix=cat_prefix_raw
        )

        # Endi qavslarni qo'shamiz (agar prefiks bo'lsa)
        # full_14_digit_code indikator bilan boshlanadi. Masalan: "101..."
        # Bizga kerakli format: "(cat_prefix_raw)qolgan_qism"
        # Yoki agar indikator ham prefiksning bir qismi bo'lsa: "(indikator + cat_prefix_raw)qolgan_qism"
        # Hozirgi talab: "(01)" bu kategoriya prefiksi. Demak, indikatorni alohida qavsga olmaymiz.

        barcode_to_save_and_display = ""
        if cat_prefix_raw:  # Agar kategoriya prefiksi mavjud bo'lsa
            # full_14_digit_code indikator + cat_prefix_raw + random_data + checksum dan iborat
            # Bizga kerak: (cat_prefix_raw) + (indikator + random_data + checksum)
            # Yoki talab "(AI) GTIN" bo'lsa, va AI = cat_prefix_raw bo'lsa:
            # AI dan keyingi qism (indikator + random + checksum)

            # Eng to'g'ri yondashuv: EAN14 standarti AI dan keyingi qismni GTIN sifatida qaraydi.
            # Agar sizning cat_prefix_raw = "01" bo'lsa, bu AI.
            # Unda full_14_digit_code "I CP RRRR C" strukturasida bo'ladi (I=indikator, CP=cat_prefix, R=random, C=checksum)
            # Bizga kerak: (CP) I RRRR C  (agar AI = CP bo'lsa)
            # Yoki (AI) DATA (bu yerda DATA = GTIN = I+CP+RRRR+C)

            # Sizning talabingiz: "(01)18456789010010"
            # Bu yerda (01) bu AI (Application Identifier), keyingi 18456789010010 bu GTIN bo'lishi mumkin.
            # Lekin EAN14 o'zi 14 raqamli GTINni kodlaydi.
            # (AI) dan keyingi ma'lumotlar alohida keladi.
            # `python-barcode` to'g'ridan-to'g'ri "(01)" kabi AI ni kodning bir qismi sifatida qo'shmaydi.
            # Uni qiymatning o'ziga qo'shishimiz kerak.

            # Keling, shunday qilamiz: cat_prefix bu AI bo'lsin.
            # Qolgan qismni (indikator + random + checksum) alohida generatsiya qilamiz.

            # AI uzunligi
            ai_len = len(cat_prefix_raw)
            # AI dan keyingi qism uchun kerakli uzunlik (checksumsiz 13 - ai_len)
            # Lekin bizda indikator ham bor. EAN14 13 ta raqamni kodlaydi + checksum.
            # Indikator (1) + AI qismi (agar AI indikatorni o'z ichiga olmasa) + qolgan_data = 13

            # Sodda yondashuv: AI ni alohida olamiz, qolgan 14 raqamni EAN14 bilan generatsiya qilamiz.
            # Lekin bu EAN14 standartiga to'liq mos kelmasligi mumkin, agar AI dan keyingi qism
            # o'zi alohida EAN14 bo'lmasa.

            # TALABGA QAYTAMIZ: "(01)18456789010010"
            # Bu yerda (01) AI.  18456789010010 esa 14 raqamli GTIN.
            # Demak, biz avval GTIN-14 ni generatsiya qilishimiz kerak, keyin oldiga (AI) ni qo'yamiz.

            # GTIN-14 uchun 13 raqamli kontentni generatsiya qilish (indikator bilan)
            # Bu yerda company_prefix ni bo'sh qoldiramiz, chunki AI ni alohida qo'shamiz
            gtin13_content = generate_ean14_content_with_checksum(
                indicator=indicator,  # Yoki boshqa indikator
                company_prefix="",  # Kompaniya prefiksi GTIN ichida bo'ladi
                item_ref_length=12  # Indikator (1) + Random (12) = 13
            )  # Bu 14 raqamli GTINni qaytaradi (checksum bilan)

            barcode_to_save_and_display = f"({cat_prefix_raw}){gtin13_content}"

        else:  # Agar kategoriya prefiksi bo'lmasa, faqat EAN-14 (indikator + 12 random + checksum)
            barcode_to_save_and_display = generate_ean14_content_with_checksum(
                indicator=indicator,
                company_prefix="",
                item_ref_length=12
            )

        if not Product.objects.filter(barcode=barcode_to_save_and_display).exists():
            return barcode_to_save_and_display

# Shtrix-kod rasmini generatsiya qilish funksiyasi (o'zgarishsiz qoladi)
def generate_barcode_image(barcode_value_from_db, barcode_type='code128',
                           writer_options=None):  # barcode_type ni Code128 ga o'zgartirdim
    """
    Shtrix-kod rasmini generatsiya qiladi. Rasm ostidagi matn sifatida
    to'liq barcode_value_from_db (masalan, "(01)123...") ishlatiladi.
    """

    # barcode_value_from_db bu biz DBda saqlagan to'liq qiymat, masalan, "(02)17750682279491"
    # Code128 bu formatni (qavslar bilan) to'g'ri qabul qila oladi.
    # EAN14 esa faqat raqamlarni kutishi mumkin. Agar (AI)GTIN ni EAN14 bilan
    # kodlashda muammo bo'lsa, Code128 yaxshiroq tanlov.

    data_to_encode = str(barcode_value_from_db).strip()

    if not data_to_encode:
        print("ERROR: Barcode value is empty for image generation.")
        return None

    # Writer options
    if writer_options is None:
        writer_options = {
            'module_height': 15.0,
            'module_width': 0.35,
            'font_size': 10,  # Matn o'lchami
            'text_distance': 5.0,  # Matn va chiziqlar orasidagi masofa
            'quiet_zone': 7.0,
            'write_text': True,  # Matnni ko'rsatish
            'human': data_to_encode  # <<<--- MUHIM: Rasm ostiga aynan shu matnni yozish
        }
    else:
        # Agar maxsus options berilsa, 'human' va 'write_text' ni o'rnatamiz
        writer_options.setdefault('write_text', True)
        writer_options.setdefault('human', data_to_encode)

    try:
        # Code128 ni ishlatamiz, chunki u (AI)GTIN formatini yaxshiroq qo'llashi mumkin
        # Agar EAN14 ishlatmoqchi bo'lsangiz va u (AI)GTIN ni qabul qilsa, barcode_type='ean14' qoldiring
        BARCODE_CLASS = barcode.get_barcode_class(barcode_type)

        instance = BARCODE_CLASS(data_to_encode, writer=ImageWriter())  # To'liq qiymatni beramiz

        buffer = BytesIO()
        # `human` opsiyasi render paytida ishlatiladi
        instance.write(buffer, options=writer_options)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    except Exception as e:
        print(f"Error generating barcode image for value '{data_to_encode}': {e}")
        import traceback
        print(traceback.format_exc())
        return None




# products/services.py
# import barcode
# from barcode.writer import ImageWriter
# from io import BytesIO
# import base64
# import random
# import string
# from .models import * # Circular import oldini olish uchun funksiya ichida
#
#
# def generate_unique_barcode_for_category(category_id=None, data_length=12, include_checksum=False):
#     """
#     Berilgan kategoriya uchun (AI)prefix(data)[checksum] formatida unikal shtrix-kod generatsiya qiladi.
#     AI (Application Identifier) kategoriya prefiksidan olinadi va qavs ichiga qo'yiladi.
#     data_length - bu AI dan keyingi ma'lumot qismining uzunligi.
#     include_checksum - Code128 o'zi checksum qo'shadi, bu parametr shart emas, lekin
#                        agar ma'lumot qismiga alohida checksum kerak bo'lsa, logikani qo'shish mumkin.
#     """
#     prefix_str = ""
#     ai_formatted_prefix = ""
#
#     if category_id:
#         try:
#             category = Category.objects.get(pk=category_id)
#             if category.barcode_prefix:
#                 prefix_str = str(category.barcode_prefix).strip()  # Ortiqcha bo'shliqlarni olib tashlash
#                 if prefix_str:  # Agar prefiks bo'sh bo'lmasa
#                     ai_formatted_prefix = f"({prefix_str})"  # Qavs ichiga olamiz
#         except Category.DoesNotExist:
#             print(f"Kategoriya ID={category_id} topilmadi, prefiks ishlatilmaydi.")
#             pass  # Kategoriya topilmasa, prefiks bo'lmaydi
#
#     # Asosiy shtrix-kod ma'lumot qismini generatsiya qilish
#     # Odatda raqamlardan iborat bo'ladi, lekin Code128 harf-raqamni qo'llaydi
#     characters_for_data = string.digits  # Faqat raqamlar
#
#     while True:
#         data_part = ''.join(random.choices(characters_for_data, k=data_length))
#
#         # To'liq shtrix-kod qiymati (AI + data)
#         # Misol: (01)123456789012
#         # Checksum ni python-barcode o'zi qo'shadi, shuning uchun uni bu yerda hisoblash shart emas.
#         full_barcode_value = ai_formatted_prefix + data_part
#
#         # Unikalligini tekshirish
#         if not Product.objects.filter(barcode=full_barcode_value).exists():
#             return full_barcode_value
#
# def generate_unique_barcode_number(length=13):
#     """
#     Unikal (tasodifiy raqamlar va harflardan iborat) shtrix-kod generatsiya qiladi.
#     EAN13 kabi standartlarga mos kelmasligi mumkin, lekin tizim ichida unikal bo'ladi.
#     Agar standart kerak bo'lsa, EAN13 generatorini implementatsiya qilish kerak.
#     """
#     while True:
#         # Tasodifiy raqamlar va/yoki harflardan iborat kod
#         # characters = string.digits # Faqat raqamlar
#         characters = string.ascii_uppercase + string.digits # Harf va raqamlar
#         code = ''.join(random.choices(characters, k=length))
#         # Modelni shu yerda import qilsak, circular import xavfi kamayadi
#         from .models import Product
#         if not Product.objects.filter(barcode=code).exists():
#             return code
#
# def generate_barcode_image(barcode_number, barcode_type='code128', writer_options=None):
#     """
#     Berilgan raqam uchun shtrix-kod rasmini base64 formatida qaytaradi.
#     """
#     if writer_options is None:
#         # Rasm parametrlarini frontend talabiga moslash mumkin
#         writer_options = {
#             'module_height': 10.0,
#             'module_width': 0.3,
#             'font_size': 8,
#             'text_distance': 4.0,
#             'quiet_zone': 2.0,
#             'write_text': True # Raqamni rasmda ko'rsatish/ko'rsatmaslik
#         }
#
#     try:
#         BARCODE_CLASS = barcode.get_barcode_class(barcode_type)
#         # barcode_number ni string ga o'tkazish muhim bo'lishi mumkin
#         instance = BARCODE_CLASS(str(barcode_number), writer=ImageWriter())
#
#         buffer = BytesIO()
#         # options ni write metodiga uzatish
#         instance.write(buffer, options=writer_options)
#         buffer.seek(0)
#         image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
#         # Data URI formatini qo'shish (frontendda rasm sifatida ishlatish uchun)
#         return f"data:image/png;base64,{image_base64}"
#     except Exception as e:
#         print(f"Error generating barcode image for '{barcode_number}': {e}") # Loglash
#         return None