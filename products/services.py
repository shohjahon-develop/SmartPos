# products/services.py
import os
import random
import string
import base64
from io import BytesIO
import barcode # To'liq import
from barcode.writer import ImageWriter # ImageWriter ni to'g'ri import qilish
from PIL import Image, ImageDraw, ImageFont
import barcode  # To'liq import
from barcode.writer import ImageWriter
from django.conf import settings

# Pillow endi kerak emas

from .models import Product, Category


def generate_unique_barcode_value(category_id=None, data_length=12):
    prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                # Prefiks faqat raqamlardan iborat ekanligiga ishonch hosil qilish
                # (Modelda RegexValidator bor, lekin bu yerda ham tekshirish mumkin)
                if str(category.barcode_prefix).strip().isdigit():
                    prefix_from_category = str(category.barcode_prefix).strip()
                else:
                    print(
                        f"WARNING: Kategoriya prefiksi '{category.barcode_prefix}' raqam emas. Prefiks ishlatilmaydi.")
        except Category.DoesNotExist:
            pass

    characters_for_data = string.digits  # <<<--- FAQAT RAQAMLAR

    while True:
        random_part = ''.join(random.choices(characters_for_data, k=data_length))
        full_barcode_value = prefix_from_category + random_part

        # Uzunlikni tekshirish (masalan, EAN13 uchun 12+1, EAN14 uchun 13+1)
        # Code128 uchun bu shart emas, lekin agar EAN ga o'xshash qilish kerak bo'lsa:
        # if len(full_barcode_value) != 12 and len(full_barcode_value) != 13: # EAN13/EAN14 uchun
        #     # Uzunlikni to'g'rilash yoki xatolik berish kerak
        #     # Hozircha Code128 uchun uzunlikni erkin qoldiramiz
        #     pass

        if not Product.objects.filter(barcode=full_barcode_value).exists():
            return full_barcode_value


# def generate_barcode_image(barcode_value_from_db, barcode_image_type='Code128', writer_options_override=None):
#     """
#     Shtrix-kod rasmini generatsiya qiladi.
#     Rasm ostidagi matnni python-barcode kutubxonasi o'zi chiqaradi.
#     """
#
#     data_to_encode = str(barcode_value_from_db).strip()
#
#     if not data_to_encode:
#         print("Xatolik: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
#         return None
#
#     # Standart writer options (python-barcode o'zi matn chiqarishi uchun)
#     default_writer_options = {
#         'module_height': 15.0,  # Chiziqlar balandligi
#         'module_width': 0.35,  # Chiziq qalinligi (printerga moslang)
#         'font_size': 10,  # Rasm ostidagi matn o'lchami
#         'text_distance': 5.0,  # Matn va chiziqlar orasidagi masofa
#         'quiet_zone': 6.5,  # Chetdagi bo'sh joy
#         'write_text': True  # <<<--- MATNNI KUTUBXONA O'ZI CHIQARADI
#         # 'human' parametrini ishlatmaymiz
#     }
#
#     final_writer_options = default_writer_options.copy()
#     if writer_options_override:
#         final_writer_options.update(writer_options_override)
#         # Agar write_text override qilinsa, o'shani ishlatamiz, aks holda True qoladi
#         final_writer_options.setdefault('write_text', True)
#
#     try:
#         BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
#         # Code128 harf-raqamlarni qabul qiladi.
#         # Agar faqat raqamlar bo'lsa (generate_unique_barcode_value dan kelganidek), bu yaxshi.
#         instance = BARCODE_CLASS(data_to_encode, writer=ImageWriter())
#
#         buffer = BytesIO()
#         instance.write(buffer, options=final_writer_options)
#         buffer.seek(0)
#         image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
#         return f"data:image/png;base64,{image_base64}"
#
#     except Exception as e:
#         print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (qiymat: {data_to_encode})")
#         import traceback
#         print(traceback.format_exc())
#         return None

def generate_barcode_image(barcode_value_to_render, barcode_image_type='Code128'):
    """
    Shtrix-kod rasmini generatsiya qiladi.
    Rasm ostidagi matn sifatida faqat barcode_value_to_render yoziladi. Narx chiqmaydi.
    """

    text_to_display = str(barcode_value_to_render).strip()
    if not text_to_display:
        print("Xatolik: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
        return None

    # Pillow bilan matn chizish uchun sozlamalar
    pil_font_size = 28  # Rasm ostidagi matn uchun shrift o'lchami
    pil_text_color = "black"
    pil_background_color = "white"
    pil_padding_top = 10  # Rasmning yuqorisidan shtrix-kod chiziqlarigacha
    pil_text_padding_from_barcode = 8  # Chiziqlar va matn orasi
    pil_padding_bottom = 10  # Matndan keyingi bo'sh joy

    # Shtrix-kod kutubxonasi uchun opsiyalar (FAQAT CHIZIQLAR, HECH QANDAY MATNSIZ)
    barcode_lib_writer_options = {
        'module_height': 12.0,  # Chiziqlar balandligi
        'module_width': 0.35,  # Chiziq qalinligi
        'quiet_zone': 1.0,  # Chiziqlar atrofidagi minimal bo'sh joy
        'write_text': False,  # <<<--- ENG MUHIM: STANDART MATNNI BUTUNLAY O'CHIRISH
        'text': '',  # <<<--- Matnni bo'sh qilish (qo'shimcha himoya)
        'background': pil_background_color,  # Orqa fon
        'foreground': pil_text_color,  # Chiziq rangi
    }

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        barcode_instance = BARCODE_CLASS(text_to_display, writer=ImageWriter())  # To'liq qiymatni kodlaymiz

        # 1. Faqat shtrix-kod chiziqlarini Pillow Image obyekti sifatida render qilish
        pil_barcode_lines_image = barcode_instance.render(writer_options=barcode_lib_writer_options)
        if pil_barcode_lines_image is None:
            print("Xatolik: barcode_instance.render() None qaytardi.")
            return None

        # 2. Shriftni yuklash
        font = None
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', "arial.ttf")  # Yoki "DejaVuSans.ttf"
        try:
            font = ImageFont.truetype(font_path, pil_font_size)
        except IOError:
            print(f"WARNING: Shrift '{font_path}' topilmadi. Tizim standartiga uriniladi.")
            try:
                font = ImageFont.truetype(None, pil_font_size)
            except Exception as e_font:
                print(f"ERROR: Shrift yuklanmadi: {e_font}"); return None
        if not font: return None

        # 3. Matn o'lchamlarini olish
        draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        try:
            text_bbox = draw_temp.textbbox((0, 0), text_to_display, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_size = draw_temp.textsize(text_to_display, font=font)
            text_width, text_height = text_size[0], text_size[1]

        # 4. Yakuniy rasm uchun o'lchamlarni hisoblash
        barcode_img_width = pil_barcode_lines_image.width
        barcode_img_height = pil_barcode_lines_image.height

        final_image_width = max(barcode_img_width, int(text_width)) + int(
            2 * barcode_lib_writer_options['quiet_zone'] * 5)  # Quiet zone ni ko'proq qo'shamiz
        final_image_height = (pil_padding_top +
                              barcode_img_height +
                              pil_text_padding_from_barcode +
                              text_height +
                              pil_padding_bottom)

        # 5. Yakuniy bo'sh rasmni yaratish
        final_image = Image.new('RGB', (final_image_width, final_image_height), pil_background_color)
        draw_final = ImageDraw.Draw(final_image)

        # 6. Shtrix-kod chiziqlarini yangi rasmga joylashtirish (markazda)
        barcode_x_pos = (final_image_width - barcode_img_width) / 2
        barcode_y_pos = pil_padding_top
        final_image.paste(pil_barcode_lines_image, (int(barcode_x_pos), int(barcode_y_pos)))

        # 7. Matnni yangi rasmga chizish (markazda, shtrix-kod ostida)
        text_x_pos = (final_image_width - text_width) / 2
        text_y_pos = barcode_y_pos + barcode_img_height + pil_text_padding_from_barcode
        draw_final.text((max(0, int(text_x_pos)), int(text_y_pos)),
                        text_to_display, font=font, fill=pil_text_color)

        # 8. Rasmni bufferga saqlash
        img_byte_arr = BytesIO()
        final_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        image_base64 = base64.b64encode(img_byte_arr.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"

    except Exception as e:
     print(f"Shtrix-kod rasmini generatsiya qilishda yakuniy xatolik: {e} (barcode_value: {barcode_value_from_db})")
    import traceback

    print(traceback.format_exc())
    return None