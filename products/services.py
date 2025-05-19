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
    full_text_to_display_on_label = str(barcode_value_from_db).strip()
    if not full_text_to_display_on_label:
        print("Xatolik: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
        return None
    data_to_encode_for_lines = full_text_to_display_on_label

    default_pil_options = {
        'font_filename': "arial.ttf",  # Standart shrift fayli nomi (loyihangizda bo'lishi kerak)
        'font_size': 28,
        'text_color': "black",
        'background_color': "white",
        'padding_top': 5,
        'barcode_height_ratio': 0.65,  # Bu endi ishlatilmaydi, chunki balandlikni Pillow bilan boshqaramiz
        'text_padding_from_barcode': 8,
        'padding_bottom': 5,
    }
    barcode_lib_writer_options = {
        'module_height': 10.0,  # Shtrix-kod chiziqlarining balandligi
        'module_width': 0.3,
        'quiet_zone': 1.0,
        'write_text': False,  # Kutubxona matnini o'chiramiz
        'background': default_pil_options['background_color'],
        'foreground': default_pil_options['text_color'],
    }
    if writer_options_override:
        barcode_lib_writer_options.update(writer_options_override)
        barcode_lib_writer_options['write_text'] = False

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        barcode_instance = BARCODE_CLASS(data_to_encode_for_lines, writer=ImageWriter())
        pil_barcode_lines_image = barcode_instance.render(writer_options=barcode_lib_writer_options)

        font = None
        # Loyiha papkasidagi static/fonts ichidan shriftni qidiramiz
        font_path_primary = os.path.join(settings.BASE_DIR, 'static', 'fonts', default_pil_options['font_filename'])
        font_path_dejavu = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')

        try:
            font = ImageFont.truetype(font_path_primary, default_pil_options['font_size'])
            print(f"INFO: Shrift ishlatildi: {font_path_primary}")
        except IOError:
            print(f"WARNING: Shrift '{font_path_primary}' topilmadi. DejaVuSans.ttf ga urinib ko'riladi.")
            try:
                font = ImageFont.truetype(font_path_dejavu, default_pil_options['font_size'])
                print(f"INFO: Shrift ishlatildi: {font_path_dejavu}")
            except IOError:
                print(f"WARNING: Shrift '{font_path_dejavu}' ham topilmadi. Tizim standartiga urinib ko'riladi.")
                try:
                    font = ImageFont.truetype(None, default_pil_options['font_size'])
                    print("INFO: Tizim standart shrifti ishlatildi.")
                except Exception as e_font_fallback:
                    print(f"ERROR: Hech qanday shrift yuklanmadi: {e_font_fallback}")
                    return None
        if not font: return None

        draw_temp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        try:
            text_bbox = draw_temp.textbbox((0, 0), full_text_to_display_on_label, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_size = draw_temp.textsize(full_text_to_display_on_label, font=font)
            text_width, text_height = text_size[0], text_size[1]

        barcode_img_width = pil_barcode_lines_image.width
        barcode_img_height = pil_barcode_lines_image.height  # <<<--- TO'G'RILANDI

        final_image_width = max(barcode_img_width, int(text_width + 2 * barcode_lib_writer_options.get('quiet_zone',
                                                                                                       1.0) * 2))  # quiet_zone ni hisobga olish
        final_image_height = (default_pil_options['padding_top'] +
                              barcode_img_height +
                              default_pil_options['text_padding_from_barcode'] +
                              text_height +
                              default_pil_options['padding_bottom'])

        final_image = Image.new('RGB', (final_image_width, final_image_height), default_pil_options['background_color'])
        draw_final = ImageDraw.Draw(final_image)

        barcode_x_pos = (final_image_width - barcode_img_width) / 2
        barcode_y_pos = default_pil_options['padding_top']
        final_image.paste(pil_barcode_lines_image, (int(barcode_x_pos), int(barcode_y_pos)))

        text_x_pos = (final_image_width - text_width) / 2
        text_y_pos = barcode_y_pos + barcode_img_height + default_pil_options['text_padding_from_barcode']
        draw_final.text((max(0, int(text_x_pos)), int(text_y_pos)),
                        full_text_to_display_on_label, font=font, fill=default_pil_options['text_color'])

        img_byte_arr = BytesIO()
        final_image.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        image_base64 = base64.b64encode(img_byte_arr.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"

    except Exception as e:
        print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (barcode_value: {barcode_value_from_db})")
        import traceback
        print(traceback.format_exc())
        return None