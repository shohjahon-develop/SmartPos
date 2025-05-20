# products/services.py
import random
import string
import base64
from io import BytesIO

import barcode  # To'liq import
from barcode.writer import ImageWriter
# Pillow endi kerak emas

from .models import Product, Category


def generate_unique_barcode_value(category_id=None, data_length=12):  # data_length ni moslang
    """
    Kategoriya prefiksi bilan (agar mavjud bo'lsa) yoki prefikssiz,
    FAQAT RAQAMLARDAN iborat unikal shtrix-kod generatsiya qiladi.
    Qavslar ishlatilmaydi.
    """
    prefix_from_category = ""
    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                # Prefiks faqat raqamlardan iborat ekanligiga ishonch hosil qilish (modelda validator bor)
                prefix_from_category = str(category.barcode_prefix).strip()
        except Category.DoesNotExist:
            pass

    # Faqat raqamlardan iborat random qism
    characters_for_data = string.digits

    while True:
        random_part = ''.join(random.choices(characters_for_data, k=data_length))
        # Prefiks + Random raqamlar
        full_barcode_value = prefix_from_category + random_part

        # Unikallik va uzunlikni tekshirish (Code128 uchun uzunlik chegarasi kengroq)
        # EAN turlari uchun aniq uzunlik kerak (masalan, EAN13 uchun 12+1, EAN14 uchun 13+1)
        # Hozir Code128 ishlatamiz, u moslashuvchan.
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

    # Standart writer options (python-barcode o'zi matn chiqarishi uchun)
    default_writer_options = {
        'module_height': 15.0,  # Chiziqlar balandligi
        'module_width': 0.35,  # Chiziq qalinligi (printerga moslang)
        'font_size': 10,  # Rasm ostidagi matn o'lchami
        'text_distance': 5.0,  # Matn va chiziqlar orasidagi masofa
        'quiet_zone': 6.5,  # Chetdagi bo'sh joy
        'write_text': True  # <<<--- MATNNI KUTUBXONA O'ZI CHIQARADI
        # 'human' parametrini ishlatmaymiz
    }

    final_writer_options = default_writer_options.copy()
    if writer_options_override:
        final_writer_options.update(writer_options_override)
        # Agar write_text override qilinsa, o'shani ishlatamiz, aks holda True qoladi
        final_writer_options.setdefault('write_text', True)

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_image_type)
        # Code128 harf-raqamlarni qabul qiladi.
        # Agar faqat raqamlar bo'lsa (generate_unique_barcode_value dan kelganidek), bu yaxshi.
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