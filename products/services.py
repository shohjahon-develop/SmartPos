# products/services.py
import os
import random
import string
import base64
from io import BytesIO
from barcode import Code128 # Yoki siz tanlagan boshqa mos tur
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont
import barcode  # barcode ni to'liq import qilamiz
# from barcode import Code128 # Endi kerak emas, barcode.Code128 orqali murojaat qilamiz
from barcode.writer import ImageWriter

# Pillow importlarini o'zgartiramiz:
import PIL  # Asosiy PIL modulini import qilamiz
from PIL import Image  # Image ni alohida import qilishimiz mumkin
from django.conf import settings

# from PIL.ImageDraw import ImageDraw # Buni PIL.ImageDraw orqali ishlatamiz
# from PIL.ImageFont import ImageFont # Buni PIL.ImageFont orqali ishlatamiz

from .models import Product, Category


def _generate_random_part(length=10):
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))


def generate_unique_barcode_value(category_id=None, data_length=10):
    prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                prefix_from_category = str(category.barcode_prefix).strip()
        except Category.DoesNotExist:
            pass
    while True:
        random_part = _generate_random_part(length=data_length)  # Yordamchi funksiyani ishlatamiz
        full_barcode_value = prefix_from_category + random_part
        if not Product.objects.filter(barcode=full_barcode_value).exists():
            return full_barcode_value


def generate_barcode_image(barcode_value_from_db, barcode_image_type='Code128', writer_options_override=None):
    text_to_display_under_barcode = str(barcode_value_from_db).strip()
    if not text_to_display_under_barcode:
        print("Xatolik: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
        return None

    # Bu qiymat faqat chiziqlarni chizish uchun ishlatiladi
    data_for_lines_encoding = text_to_display_under_barcode

    # Pillow bilan matn chizish uchun standart sozlamalar
    pil_options = {
        'font_filename': "arial.ttf",  # Yoki "DejaVuSans.ttf"
        'font_size': 28,  # Chop etish uchun shrift o'lchami
        'text_color': "black",
        'background_color': "white",
        'padding_top': 5,  # Rasmning yuqorisidan shtrix-kodgacha
        'text_padding_from_barcode': 5,  # Shtrix-kod va matn orasi
        'padding_bottom': 5,  # Matndan keyingi bo'sh joy
        'image_width': 300,  # Chiqish rasmning taxminiy eni (kerak bo'lsa sozlang)
        'barcode_strip_height': 60,  # Faqat shtrix-kod chiziqlarining balandligi
    }

    # Shtrix-kod kutubxonasi uchun opsiyalar (FAQAT CHIZIQLAR, MATNSIZ)
    barcode_lib_writer_options = {
        'module_height': pil_options['barcode_strip_height'] / 50,  # Bu ImageWriter uchun nisbiy qiymat
        'module_width': 0.3,  # Chiziq qalinligi
        'quiet_zone': 0.5,  # Juda kichik, chunki paddingni o'zimiz boshqaramiz
        'write_text': False,  # <<<--- ENG MUHIM: STANDART MATNNI O'CHIRISH
        'text': '',  # <<<--- Ba'zi writerlar uchun matnni bo'sh qilish
        'background': pil_options['background_color'],
        'foreground': pil_options['text_color'],
    }

    if writer_options_override:  # Tashqaridan kelgan opsiyalarni qo'shish
        barcode_lib_writer_options.update(writer_options_override)
        # write_text va text ni qayta o'rnatish, ular har doim matnsiz bo'lishi uchun
        barcode_lib_writer_options['write_text'] = False
        barcode_lib_writer_options['text'] = ''

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        barcode_instance = BARCODE_CLASS(data_for_lines_encoding, writer=ImageWriter())

        # 1. Shtrix-kod chiziqlarini (MATNSIZ) Pillow Image obyekti sifatida render qilish
        # writer_options ni render ga uzatamiz
        pil_barcode_lines_image = barcode_instance.render(writer_options=barcode_lib_writer_options)

        # 2. Shriftni yuklash
        font = None
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', pil_options['font_filename'])
        try:
            font = ImageFont.truetype(font_path, pil_options['font_size'])
        except IOError:
            print(f"WARNING: Shrift '{font_path}' topilmadi. Tizim standartiga uriniladi.")
            try:
                font = ImageFont.truetype(None, pil_options['font_size'])
            except Exception as e_font:
                print(f"ERROR: Shrift yuklanmadi: {e_font}"); return None
        if not font: return None

        # 3. Matn o'lchamlarini olish
        draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        try:
            text_bbox = draw_temp.textbbox((0, 0), text_to_display_under_barcode, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_size = draw_temp.textsize(text_to_display_under_barcode, font=font)
            text_width, text_height = text_size[0], text_size[1]

        # 4. Yakuniy rasm uchun o'lchamlarni hisoblash
        # Shtrix-kod chiziqlarining haqiqiy balandligi (render qilingandan keyin)
        actual_barcode_strip_height = pil_barcode_lines_image.height
        # Shtrix-kod chiziqlarining haqiqiy eni (render qilingandan keyin)
        actual_barcode_strip_width = pil_barcode_lines_image.width

        # Yakuniy rasm eni (matn yoki shtrix-kodning eng kengiga qarab + padding)
        final_image_width = max(actual_barcode_strip_width, int(text_width)) + int(
            2 * barcode_lib_writer_options['quiet_zone'] * 10)  # Taxminiy
        # Yakuniy rasm balandligi
        final_image_height = (pil_options['padding_top'] +
                              actual_barcode_strip_height +
                              pil_options['text_padding_from_barcode'] +
                              text_height +
                              pil_options['padding_bottom'])

        # 5. Yakuniy bo'sh rasmni yaratish
        final_image = Image.new('RGB', (final_image_width, final_image_height), pil_options['background_color'])
        draw_final = ImageDraw.Draw(final_image)

        # 6. Shtrix-kod chiziqlarini yangi rasmga joylashtirish (gorizontal markazda)
        barcode_x_pos = (final_image_width - actual_barcode_strip_width) / 2
        barcode_y_pos = pil_options['padding_top']
        final_image.paste(pil_barcode_lines_image, (int(barcode_x_pos), int(barcode_y_pos)))

        # 7. Matnni yangi rasmga chizish (gorizontal markazda, shtrix-kod ostida)
        text_x_pos = (final_image_width - text_width) / 2
        text_y_pos = barcode_y_pos + actual_barcode_strip_height + pil_options['text_padding_from_barcode']
        draw_final.text((max(0, int(text_x_pos)), int(text_y_pos)),
                        text_to_display_under_barcode,
                        font=font,
                        fill=pil_options['text_color'])

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