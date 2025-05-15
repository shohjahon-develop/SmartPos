#
# products/services.py
import random
import string

import barcode
from PIL.ImageDraw import ImageDraw
from PIL.ImageFont import ImageFont
from barcode import EAN14  # EAN14 ni import qilamiz
from barcode.writer import ImageWriter  # Bu generate_barcode_image uchun
from io import BytesIO
import base64
from .models import Product, Category


def _generate_gtin13_content(indicator='1', company_and_item_ref_length=12):
    """EAN-14 uchun 13 raqamli GTIN kontentini (checksumsiz) generatsiya qiladi."""
    if not (indicator.isdigit() and len(indicator) == 1 and 0 <= int(indicator) <= 8):
        indicator = '1'  # Standart indikator

    # Indikatordan keyin qolgan raqamlar soni
    random_digits_needed = company_and_item_ref_length
    if (len(indicator) + random_digits_needed) != 13:  # Jami 13 raqam bo'lishi kerak (checksumsiz)
        # Bu logikani ehtiyojga qarab sozlash kerak
        random_digits_needed = 12  # Default holatda indikator + 12 random raqam

    random_part = ''.join(random.choices(string.digits, k=random_digits_needed))
    return indicator + random_part


def generate_unique_ean14_for_product(category_id=None, indicator='1'):
    """
    Mahsulot uchun unikal shtrix-kodni (AI bilan birga, masalan, "(01)123...") generatsiya qiladi.
    Bu DBga yoziladigan va API orqali qaytariladigan qiymat.
    """
    ai_prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                ai_prefix_from_category = str(category.barcode_prefix).strip()
        except Category.DoesNotExist:
            pass

    while True:
        # EAN-14 uchun 13 raqamli asosiy qismni generatsiya qilamiz
        # Bu qism AI ni o'z ichiga olmaydi, faqat Indikator + Kompaniya/Mahsulot kodi
        gtin13_content = _generate_gtin13_content(indicator=indicator)  # Bu 13 raqamli

        try:
            ean14_obj = EAN14(gtin13_content)  # 13 raqam beriladi, checksum qo'shiladi
            gtin14_with_checksum = ean14_obj.ean  # Bu 14 raqamli GTIN
        except Exception as e:
            print(f"Xatolik (EAN14 obyektini yaratish): {e}, Kontent: {gtin13_content}")
            continue  # Qayta urinish

        # Yakuniy shtrix-kod (AI bilan, agar mavjud bo'lsa)
        if ai_prefix_from_category:
            final_barcode_value = f"({ai_prefix_from_category}){gtin14_with_checksum}"
        else:
            final_barcode_value = gtin14_with_checksum  # AI siz EAN-14

        if not Product.objects.filter(barcode=final_barcode_value).exists():
            return final_barcode_value


def generate_barcode_image(barcode_value_from_db, barcode_type_for_encoding='ean14', writer_options=None):
    """
    Berilgan shtrix-kod qiymati uchun rasm generatsiya qiladi.
    Rasm ostidagi matn sifatida to'liq barcode_value_from_db (AI bilan) ishlatiladi.
    barcode_type_for_encoding - chiziqlarni qaysi standartda chizishni belgilaydi.
    """
    full_barcode_text_to_display = str(barcode_value_from_db).strip()

    # Rasm chizish uchun faqat raqamli GTIN qismini olamiz (AI va qavslarsiz)
    data_to_encode_for_lines = full_barcode_text_to_display
    if data_to_encode_for_lines.startswith("(") and ")" in data_to_encode_for_lines:
        try:
            data_to_encode_for_lines = data_to_encode_for_lines.split(")", 1)[1]
        except IndexError:
            pass

    if not data_to_encode_for_lines.isdigit():
        print(f"Rasm uchun yaroqsiz raqamli qism: '{data_to_encode_for_lines}' (asl: '{full_barcode_text_to_display}')")
        return None

    # EAN14 klassi 13 (checksumsiz) yoki 14 (checksum bilan) raqamli stringni kutadi.
    content_for_barcode_lib = ""
    if len(data_to_encode_for_lines) == 14:
        content_for_barcode_lib = data_to_encode_for_lines[:-1]  # Checksumsiz 13 raqam
    elif len(data_to_encode_for_lines) == 13:
        content_for_barcode_lib = data_to_encode_for_lines  # Checksumsiz 13 raqam
    else:
        print(
            f"EAN14 uchun yaroqsiz uzunlikdagi raqamli qism: {len(data_to_encode_for_lines)} (asl: '{full_barcode_text_to_display}')")
        return None

    # Pillow yordamida rasm chizish uchun standart writer_options
    # Matnni o'zimiz chizganimiz uchun 'write_text': False
    default_writer_opts = {
        'module_height': 15.0,
        'module_width': 0.35,
        'quiet_zone': 3.0,  # Matn sig'ishi uchun biroz kattaroq
        'font_size': 25,  # Pillow uchun shrift o'lchami
        'text_distance': 7.0,  # Matn va shtrix-kod orasidagi masofa
        'background': 'white',
        'foreground': 'black',
        'write_text': False  # Kutubxona matnini o'chiramiz
    }
    if writer_options:
        default_writer_opts.update(writer_options)

    final_writer_options = default_writer_opts

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_type_for_encoding)
        # Kutubxonaga faqat raqamli qismni beramiz
        instance = BARCODE_CLASS(content_for_barcode_lib, writer=ImageWriter())

        # Rasmning o'zini bufferga chizish (matnsiz)
        img_buffer = BytesIO()
        # instance.write(img_buffer, options=final_writer_options) # options ni write ga beramiz
        # Yoki render ni ishlatish:
        rendered_pil_image = instance.render(writer_options=final_writer_options)  # Bu Pillow Image obyektini qaytaradi

        # Pillow yordamida o'zimizning matnimizni qo'shamiz
        draw = ImageDraw.Draw(rendered_pil_image)

        try:
            # Shriftni yuklash (serverda mavjud bo'lishi kerak yoki standart shrift)
            font = ImageFont.truetype("arial.ttf", final_writer_options['font_size'])
        except IOError:
            font = ImageFont.load_default()
            print("WARNING: Arial.ttf topilmadi, standart shrift ishlatildi.")

        # Matn o'lchamini olish (Pillow 9.2.0+ uchun)
        try:
            text_bbox = draw.textbbox((0, 0), full_barcode_text_to_display, font=font)
            text_width = text_bbox[2] - text_bbox[0]
        except AttributeError:  # Eski Pillow versiyalari
            text_width = draw.textlength(full_barcode_text_to_display, font=font)

        # Matn pozitsiyasi (gorizontal markazda, shtrix-kodning pastida)
        img_width, img_height = rendered_pil_image.size
        text_x = (img_width - text_width) / 2
        text_y = img_height - (final_writer_options['font_size'] * 1.2)  # Taxminiy joylashuv

        draw.text((text_x, text_y), full_barcode_text_to_display, font=font, fill=final_writer_options['foreground'])

        # Yangilangan rasmni bufferga saqlash
        final_img_buffer = BytesIO()
        rendered_pil_image.save(final_img_buffer, format="PNG")
        final_img_buffer.seek(0)

        image_base64 = base64.b64encode(final_img_buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"

    except Exception as e:
        print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e}")
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