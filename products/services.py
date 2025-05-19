# products/services.py
import random
import string
import base64
from io import BytesIO

import barcode
from barcode import Code128  # Yoki EAN13, agar faqat raqamlar va checksum kerak bo'lsa
from barcode.writer import ImageWriter
# Pillow endi matn chizish uchun kerak emas

from .models import Product, Category


def _generate_random_part(length=10):
    """Berilgan uzunlikda tasodifiy harf-raqamli qator generatsiya qiladi."""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=length))


def generate_unique_barcode_value(category_id=None,
                                  data_length=10):  # Indikator olib tashlandi, EAN-14 ga bog'liqlik kamaydi
    """
    Kategoriya prefiksi bilan (agar mavjud bo'lsa) yoki prefikssiz unikal shtrix-kod generatsiya qiladi.
    Format: "PREFIX_RANDOM_DATA" yoki "RANDOM_DATA".
    """
    prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                prefix_from_category = str(category.barcode_prefix).strip()
        except Category.DoesNotExist:
            pass

    characters_for_data = string.ascii_uppercase + string.digits

    while True:
        random_part = ''.join(random.choices(characters_for_data, k=data_length))
        full_barcode_value = prefix_from_category + random_part

        if not Product.objects.filter(barcode=full_barcode_value).exists():
            return full_barcode_value


def generate_barcode_image(barcode_value_from_db, barcode_image_type='Code128', writer_options=None):
    """
    Berilgan shtrix-kod qiymati uchun rasm generatsiya qiladi.
    Rasm ostidagi matn sifatida shu barcode_value_from_db ishlatiladi.
    """
    data_to_encode_and_display = str(barcode_value_from_db).strip()
    if not data_to_encode_and_display: return None

    if writer_options is None:
        writer_options = {
            'module_height': 15.0, 'module_width': 0.3,
            'font_size': 10, 'text_distance': 5.0,
            'quiet_zone': 6.5, 'write_text': True,
            'human': data_to_encode_and_display
        }
    else:
        writer_options.setdefault('write_text', True)
        writer_options.setdefault('human', data_to_encode_and_display)

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        instance = BARCODE_CLASS(data_to_encode_and_display, writer=ImageWriter())
        buffer = BytesIO()
        instance.write(buffer, options=writer_options)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    except Exception as e:
        print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (qiymat: {data_to_encode_and_display})")
        return None