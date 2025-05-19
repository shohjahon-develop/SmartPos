# products/services.py
import random
import string
import base64
from io import BytesIO

import barcode  # barcode ni to'liq import qilamiz
# from barcode import Code128 # Endi kerak emas, barcode.Code128 orqali murojaat qilamiz
from barcode.writer import ImageWriter

# Pillow importlarini o'zgartiramiz:
import PIL  # Asosiy PIL modulini import qilamiz
from PIL import Image  # Image ni alohida import qilishimiz mumkin
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


def generate_barcode_image(barcode_value_from_db, barcode_image_type='Code128', writer_options=None):
    full_text_to_display_on_label = str(barcode_value_from_db).strip()
    if not full_text_to_display_on_label:
        print("ERROR: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
        return None

    data_to_encode_for_lines = full_text_to_display_on_label

    default_writer_opts = {
        'module_height': 10.0, 'module_width': 0.3,
        'quiet_zone': 2.0, 'font_size': 25,
        'text_distance': 8.0, 'background': 'white',
        'foreground': 'black', 'write_text': False
    }
    final_writer_options = default_writer_opts.copy()
    if writer_options:
        final_writer_options.update(writer_options)
    final_writer_options['write_text'] = False

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        barcode_instance = BARCODE_CLASS(data_to_encode_for_lines, writer=ImageWriter())
        pil_image_barcode_only = barcode_instance.render(writer_options=final_writer_options)

        # Pillow obyektlariga PIL.<ModulNomi> orqali murojaat qilamiz
        draw = PIL.ImageDraw.Draw(pil_image_barcode_only)
        font = None
        try:
            font = PIL.ImageFont.truetype("DejaVuSans.ttf", final_writer_options['font_size'])
        except IOError:
            print("WARNING: DejaVuSans.ttf topilmadi, standart PIL shrifti ishlatiladi.")
            try:
                font = PIL.ImageFont.load_default()
            except AttributeError:
                try:
                    font = PIL.ImageFont.truetype(None, final_writer_options['font_size'])
                except Exception as e_font_fallback:
                    print(f"ERROR: Hech qanday shrift yuklanmadi: {e_font_fallback}")
                    return None
        if not font:
            print("ERROR: Matn uchun shrift topilmadi.")
            return None

        draw_temp = PIL.ImageDraw.Draw(Image.new('RGB', (1, 1)))
        try:
            text_bbox = draw_temp.textbbox((0, 0), full_text_to_display_on_label, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
        except AttributeError:
            text_size = draw_temp.textsize(full_text_to_display_on_label, font=font)  # Eski Pillow
            text_width = text_size[0]
            text_height = text_size[1]

        padding_below_barcode = int(final_writer_options.get('text_distance', 5.0))
        total_new_height = pil_image_barcode_only.height + padding_below_barcode + text_height + int(
            final_writer_options.get('quiet_zone', 2.0) / 2)
        effective_barcode_width = pil_image_barcode_only.width
        new_image_width = max(effective_barcode_width,
                              int(text_width + 2 * final_writer_options.get('quiet_zone', 2.0)))

        final_image = Image.new('RGB', (new_image_width, total_new_height), final_writer_options['background'])
        draw_final = PIL.ImageDraw.Draw(final_image)  # Draw ni bu yerda ham PIL.ImageDraw orqali
        barcode_x_offset = (new_image_width - pil_image_barcode_only.width) / 2
        final_image.paste(pil_image_barcode_only, (int(barcode_x_offset), 0))
        text_x_final = (new_image_width - text_width) / 2
        text_y_final = pil_image_barcode_only.height + padding_below_barcode
        draw_final.text((text_x_final if text_x_final > 0 else 0, text_y_final),
                        full_text_to_display_on_label,
                        font=font,
                        fill=final_writer_options['foreground'])

        final_img_buffer = BytesIO()
        final_image.save(final_img_buffer, format="PNG")
        final_img_buffer.seek(0)
        image_base64 = base64.b64encode(final_img_buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"

    except Exception as e:
        print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (barcode_value: {barcode_value_from_db})")
        import traceback
        print(traceback.format_exc())
        return None