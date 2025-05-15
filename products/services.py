# products/services.py
import random
import string
import base64
from io import BytesIO

import barcode
from barcode import Code128  # Yoki EAN13, agar faqat raqamlar kerak bo'lsa va checksum bilan
from barcode.writer import ImageWriter
# Pillow endi kerak emas, chunki 'human' opsiyasi ishlatiladi

from .models import Product, Category


def generate_unique_barcode_value(category_id=None, data_length=10, include_indicator=True):
    """
    Kategoriya prefiksi bilan (agar mavjud bo'lsa) yoki prefikssiz unikal shtrix-kod generatsiya qiladi.
    Format: "[INDIKATOR]PREFIX_RANDOM_DATA[CHECKSUM_AGAR_EAN_BO'LSA]".
    Code128 o'zi checksum qo'ymaydi, lekin EAN turlari qo'yadi.
    data_length - bu prefiks va indikatordan keyingi tasodifiy qismning uzunligi.
    """
    prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                prefix_from_category = str(category.barcode_prefix).strip()
        except Category.DoesNotExist:
            pass

    indicator = "1" if include_indicator else ""  # EAN uchun indikator, Code128 uchun shart emas

    # Code128 uchun harf-raqam ishlatamiz
    characters_for_data = string.ascii_uppercase + string.digits

    # Prefiks va indikator uzunligini hisobga olib, qolgan qism uchun uzunlik
    # Lekin biz data_length ni faqat random qism uchun deb belgilaymiz.
    # Jami uzunlik prefiks + data_length (+ indikator agar EAN bo'lsa) bo'ladi.

    while True:
        random_part = ''.join(random.choices(characters_for_data, k=data_length))

        # EAN formatiga o'xshatish uchun indikatorni boshiga qo'yishimiz mumkin
        # lekin Code128 uchun bu shart emas. Hozircha faqat prefiks va random.
        # Agar EAN14 ga o'xshash 14 raqamli kod kerak bo'lsa, bu logikani o'zgartirish kerak.
        # Hozirgi talab: PREFIX + RANDOM

        full_barcode_value = prefix_from_category + random_part

        if not Product.objects.filter(barcode=full_barcode_value).exists():
            return full_barcode_value


def generate_barcode_image(barcode_value_from_db, barcode_image_type='Code128', writer_options=None):
    """
    Berilgan shtrix-kod qiymati uchun rasm generatsiya qiladi.
    Rasm ostidagi matn sifatida shu barcode_value_from_db ishlatiladi.
    """
    data_to_encode_and_display = str(barcode_value_from_db).strip()

    if not data_to_encode_and_display:
        print("Xatolik: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
        return None

    # Writer options (matn chiqishi uchun write_text: True va human parametri)
    if writer_options is None:
        writer_options = {
            'module_height': 15.0,
            'module_width': 0.3,
            'font_size': 10,
            'text_distance': 5.0,
            'quiet_zone': 6.5,
            'write_text': True,  # Matnni ko'rsatishni yoqamiz
            'human': data_to_encode_and_display  # Aynan shu matnni chiqarish uchun
        }
    else:
        writer_options.setdefault('write_text', True)
        writer_options.setdefault('human', data_to_encode_and_display)

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        # Code128 (yoki boshqa tanlangan tur) to'liq qiymatni (prefiks bilan) kodlaydi
        instance = BARCODE_CLASS(data_to_encode_and_display, writer=ImageWriter())

        buffer = BytesIO()
        instance.write(buffer, options=writer_options)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"

    except Exception as e:
        print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (qiymat: {data_to_encode_and_display})")
        # import traceback
        # print(traceback.format_exc())
        return None
#
# def generate_unique_ean14_for_product(category_id=None, indicator='1'):
#     """
#     EAN-14 (GTIN-14) uchun 13 raqamli asosiy kontentni (indikator + 12 tasodifiy raqam) generatsiya qiladi.
#     Bu qismga AI kirmaydi. Checksum keyin qo'shiladi.
#     """
#     if not (indicator.isdigit() and len(indicator) == 1 and 0 <= int(indicator) <= 8):
#         indicator = '1'  # Standart indikator
#
#     random_part_length = 12  # Indikator (1) + Random (12) = 13
#     random_part = ''.join(random.choices(string.digits, k=random_part_length))
#     return indicator + random_part
#
#
# def generate_unique_barcode_value(category_id=None, indicator='1'):
#     """
#     DBga saqlanadigan va API orqali qaytariladigan to'liq shtrix-kod qiymatini generatsiya qiladi.
#     Format: "(AI)GTIN-14" yoki "GTIN-14".
#     """
#     ai_prefix_from_category = ""
#     if category_id:
#         try:
#             category = Category.objects.get(pk=category_id)
#             if category.barcode_prefix:
#                 ai_prefix_from_category = str(category.barcode_prefix).strip()
#         except Category.DoesNotExist:
#             pass
#
#     while True:
#         gtin13_content = _generate_gtin13_content_for_ean(indicator=indicator)
#
#         try:
#             # EAN14 klassi yordamida checksum bilan 14 raqamli GTINni olamiz
#             # Bu yerda python-barcode ning EAN14 klassini faqat checksum uchun ishlatamiz
#             from barcode import EAN14 as EAN14_calculator
#             ean14_calc_obj = EAN14_calculator(gtin13_content)
#             gtin14_with_checksum = ean14_calc_obj.ean
#         except Exception as e:
#             print(f"Xatolik (EAN14 checksum hisoblash): {e}, Kontent: {gtin13_content}")
#             continue  # Qayta urinish
#
#         # Yakuniy shtrix-kod (AI bilan, agar mavjud bo'lsa)
#         if ai_prefix_from_category:
#             final_barcode_value = f"({ai_prefix_from_category}){gtin14_with_checksum}"
#         else:
#             final_barcode_value = gtin14_with_checksum
#
#         if not Product.objects.filter(barcode=final_barcode_value).exists():
#             return final_barcode_value
#
#
# def generate_barcode_image(barcode_value_from_db, writer_options=None):
#     """
#     Berilgan shtrix-kod qiymati uchun rasm generatsiya qiladi.
#     Rasm ostidagi matn sifatida to'liq barcode_value_from_db ishlatiladi.
#     Chiziqlar Code128 standarti bo'yicha chiziladi.
#     """
#
#     full_text_to_display_and_encode = str(barcode_value_from_db).strip()
#
#     if not full_text_to_display_and_encode:
#         print("ERROR: Barcode value is empty for image generation.")
#         return None
#
#     # Pillow yordamida rasm chizish uchun standart writer_options
#     default_writer_opts = {
#         'module_height': 12.0,  # Balandlikni biroz kamaytirdim
#         'module_width': 0.3,  # Chiziq qalinligi (standartroq)
#         'quiet_zone': 6.0,  # Chetdagi bo'sh joy
#         'font_size': 28,  # Shrift o'lchami (kattaroq)
#         'text_distance': 6.0,  # Matn va shtrix-kod orasidagi masofa
#         'background': 'white',
#         'foreground': 'black',
#         'write_text': False  # Kutubxona matnini o'chiramiz, o'zimiz chizamiz
#     }
#     if writer_options:  # Agar maxsus opsiyalar berilsa, ularni birlashtiramiz
#         current_options = default_writer_opts.copy()
#         current_options.update(writer_options)
#         final_writer_options = current_options
#     else:
#         final_writer_options = default_writer_opts
#
#     # write_text har doim False bo'lishi kerak, chunki matnni Pillow bilan chizamiz
#     final_writer_options['write_text'] = False
#
#     try:
#         # Chiziqlarni generatsiya qilish uchun Code128 ni ishlatamiz,
#         # chunki u (AI)GTIN formatini yaxshi qabul qiladi.
#         barcode_encoder = Code128(full_text_to_display_and_encode, writer=ImageWriter())
#
#         # Rasmning o'zini (matnsiz) bufferga chizish
#         # instance.render() Pillow Image obyektini qaytaradi
#         pil_image_without_text = barcode_encoder.render(writer_options=final_writer_options)
#
#         # Pillow yordamida o'zimizning matnimizni qo'shamiz
#         draw = ImageDraw.Draw(pil_image_without_text)
#
#         font = None
#         try:
#             # Shriftni yuklash
#             # PythonAnywhere da standart shriftlardan foydalanish yaxshiroq
#             # Yoki shrift faylini loyihaga qo'shib, unga yo'l ko'rsatish kerak
#             # Masalan, "DejaVuSans.ttf" ko'p Linux tizimlarida mavjud
#             font = ImageFont.truetype("DejaVuSans.ttf", final_writer_options['font_size'])
#         except IOError:
#             print("WARNING:DejaVuSans.ttf topilmadi, standart PIL shrifti ishlatiladi.")
#             try:
#                 font = ImageFont.load_default()  # Yangi Pillow versiyalarida bu yo'q
#             except AttributeError:  # Agar load_default yo'q bo'lsa
#                 # Pillow 10+ uchun standart shriftni shunday olish mumkin
#                 try:
#                     font = ImageFont.truetype(None, final_writer_options['font_size'])  # Default system font
#                 except Exception as e_font_fallback:
#                     print(f"ERROR: Could not load any font: {e_font_fallback}")
#                     return None  # Shrift umuman topilmasa
#
#         if not font:  # Double check
#             print("ERROR: Matn uchun shrift topilmadi (yakuniy tekshiruv).")
#             return None
#
#         # Matn o'lchamini olish
#         try:
#             text_bbox = draw.textbbox((0, 0), full_text_to_display_and_encode, font=font)
#             text_width = text_bbox[2] - text_bbox[0]
#             # text_height = text_bbox[3] - text_bbox[1] # Hozircha kerak emas
#         except AttributeError:  # Eski Pillow
#             text_size = draw.textlength(full_text_to_display_and_encode, font=font)  # Faqat enini beradi
#             text_width = text_size
#
#         # Matn pozitsiyasi
#         img_width, img_height = pil_image_without_text.size
#         text_x = (img_width - text_width) / 2
#         # text_y ni shtrix-kod chiziqlarining pastki qismiga yaqinroq joylashtiramiz
#         # Bu module_height va text_distance ga bog'liq bo'ladi
#         # Taxminan:
#         text_y = final_writer_options['module_height'] + final_writer_options['text_distance'] - (
#                     final_writer_options['font_size'] * 0.2)  # Yoki img_height - font_size * 1.5
#
#         # Rasm balandligini matn sig'ishi uchun biroz oshirishimiz mumkin
#         # Yoki matnni shtrix-kod ostidagi bo'sh joyga (agar writer opsiyalari to'g'ri sozlangan bo'lsa) chizamiz
#         # Hozircha, rasm o'lchamini o'zgartirmaymiz, text_y ni to'g'ri tanlashga harakat qilamiz.
#         # text_y ni module_height dan pastroqqa qo'yish kerak.
#
#         # Eng yaxshi yondashuv: Rasm balandligini matn uchun yetarli joy qoldiradigan qilib oshirish.
#         # Buning uchun yangi bo'sh rasm yaratib, unga shtrix-kodni va matnni chizish kerak.
#         # Hozircha sodda variant:
#
#         # Matnni chizish
#         draw.text((text_x if text_x > 0 else 0, text_y), full_text_to_display_and_encode, font=font,
#                   fill=final_writer_options['foreground'])
#
#         final_img_buffer = BytesIO()
#         pil_image_without_text.save(final_img_buffer, format="PNG")
#         final_img_buffer.seek(0)
#
#         image_base64 = base64.b64encode(final_img_buffer.read()).decode('utf-8')
#         return f"data:image/png;base64,{image_base64}"
#
#     except Exception as e:
#         print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (barcode_value: {barcode_value_from_db})")
#         import traceback
#         print(traceback.format_exc())
#         return None