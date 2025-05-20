# products/services.py
import random
import string  # Bu endi string.digits uchun kerak
import base64
from io import BytesIO

import barcode
from barcode.writer import ImageWriter

from .models import Product, Category


def generate_unique_barcode_value(category_id=None, data_length=9):  # DATA_LENGTH NI 9 QILDIK
    """
    Kategoriya prefiksi bilan (agar mavjud bo'lsa) yoki prefikssiz,
    FAQAT RAQAMLARDAN iborat unikal shtrix-kod generatsiya qiladi.
    Qavslar ishlatilmaydi. data_length - bu tasodifiy raqamlar qismining uzunligi.
    """
    prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                # Prefiks faqat raqamlardan iborat ekanligiga ishonch hosil qilish
                # Modelda RegexValidator(r'^[0-9]*$') bo'lishi kerak
                prefix_from_category = str(category.barcode_prefix).strip()
                if not prefix_from_category.isdigit():
                    print(
                        f"WARNING: Kategoriya prefiksi '{prefix_from_category}' raqam emas. Prefiks e'tiborga olinmaydi.")
                    prefix_from_category = ""  # Agar raqam bo'lmasa, ishlatmaymiz
        except Category.DoesNotExist:
            pass

    # Faqat raqamlardan iborat random qism
    characters_for_data = string.digits

    while True:
        random_part = ''.join(random.choices(characters_for_data, k=data_length))
        # Prefiks + Random raqamlar
        full_barcode_value = prefix_from_category + random_part

        # Skanerlar uchun Code128 yaxshi, lekin agar faqat raqamlar bo'lsa, EAN turi ham bo'lishi mumkin.
        # Uzunlikni tekshirish: Agar siz EAN standartiga o'tmoqchi bo'lsangiz,
        # masalan EAN-13 uchun full_barcode_value 12 raqamli bo'lishi kerak (13-chi checksum).
        # Hozircha umumiy uzunlikni tekshirmaymiz, Code128 ga ishonamiz.

        if not Product.objects.filter(barcode=full_barcode_value).exists():
            return full_barcode_value


def generate_barcode_image(barcode_value_from_db, barcode_image_type='Code128', writer_options_override=None):
    """
    Shtrix-kod rasmini generatsiya qiladi.
    Rasm ostidagi matnni python-barcode kutubxonasi o'zi chiqaradi.
    """

    data_to_encode = str(barcode_value_from_db).strip()
    if not data_to_encode:
        print("Xatolik: Shtrix-kod qiymati rasm generatsiyasi uchun bo'sh.")
        return None

    # Standart writer options
    default_writer_options = {
        'module_height': 15.0,  # Balandlikni oshirish mumkin (masalan, 15.0 - 20.0)
        'module_width': 0.3,  # Chiziq qalinligi (0.2 dan 0.5 gacha sinab ko'ring)
        'font_size': 10,  # Matn o'lchami
        'text_distance': 5.0,  # Matn va chiziqlar orasidagi masofa
        'quiet_zone': 7.0,  # Chetdagi bo'sh joy (skaner uchun muhim)
        'write_text': True  # Matnni chiqarish
    }

    final_writer_options = default_writer_options.copy()
    if writer_options_override:
        final_writer_options.update(writer_options_override)
    final_writer_options.setdefault('write_text', True)

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        # Code128 qisqa raqamli kodlarni ham yaxshi qabul qiladi.
        instance = BARCODE_CLASS(data_to_encode, writer=ImageWriter())

        buffer = BytesIO()
        instance.write(buffer, options=final_writer_options)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"

    except Exception as e:
        print(f"Shtrix-kod rasmini generatsiya qilishda xatolik: {e} (qiymat: {data_to_encode})")
        import traceback
        print(traceback.format_exc())
        return None