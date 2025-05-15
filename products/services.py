# products/services.py
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
import random
import string
from .models import * # Circular import oldini olish uchun funksiya ichida


def generate_unique_barcode_for_category(category_id=None, data_length=12, include_checksum=False):
    """
    Berilgan kategoriya uchun (AI)prefix(data)[checksum] formatida unikal shtrix-kod generatsiya qiladi.
    AI (Application Identifier) kategoriya prefiksidan olinadi va qavs ichiga qo'yiladi.
    data_length - bu AI dan keyingi ma'lumot qismining uzunligi.
    include_checksum - Code128 o'zi checksum qo'shadi, bu parametr shart emas, lekin
                       agar ma'lumot qismiga alohida checksum kerak bo'lsa, logikani qo'shish mumkin.
    """
    prefix_str = ""
    ai_formatted_prefix = ""

    if category_id:
        try:
            category = Category.objects.get(pk=category_id)
            if category.barcode_prefix:
                prefix_str = str(category.barcode_prefix).strip()  # Ortiqcha bo'shliqlarni olib tashlash
                if prefix_str:  # Agar prefiks bo'sh bo'lmasa
                    ai_formatted_prefix = f"({prefix_str})"  # Qavs ichiga olamiz
        except Category.DoesNotExist:
            print(f"Kategoriya ID={category_id} topilmadi, prefiks ishlatilmaydi.")
            pass  # Kategoriya topilmasa, prefiks bo'lmaydi

    # Asosiy shtrix-kod ma'lumot qismini generatsiya qilish
    # Odatda raqamlardan iborat bo'ladi, lekin Code128 harf-raqamni qo'llaydi
    characters_for_data = string.digits  # Faqat raqamlar

    while True:
        data_part = ''.join(random.choices(characters_for_data, k=data_length))

        # To'liq shtrix-kod qiymati (AI + data)
        # Misol: (01)123456789012
        # Checksum ni python-barcode o'zi qo'shadi, shuning uchun uni bu yerda hisoblash shart emas.
        full_barcode_value = ai_formatted_prefix + data_part

        # Unikalligini tekshirish
        if not Product.objects.filter(barcode=full_barcode_value).exists():
            return full_barcode_value

def generate_unique_barcode_number(length=13):
    """
    Unikal (tasodifiy raqamlar va harflardan iborat) shtrix-kod generatsiya qiladi.
    EAN13 kabi standartlarga mos kelmasligi mumkin, lekin tizim ichida unikal bo'ladi.
    Agar standart kerak bo'lsa, EAN13 generatorini implementatsiya qilish kerak.
    """
    while True:
        # Tasodifiy raqamlar va/yoki harflardan iborat kod
        # characters = string.digits # Faqat raqamlar
        characters = string.ascii_uppercase + string.digits # Harf va raqamlar
        code = ''.join(random.choices(characters, k=length))
        # Modelni shu yerda import qilsak, circular import xavfi kamayadi
        from .models import Product
        if not Product.objects.filter(barcode=code).exists():
            return code

def generate_barcode_image(barcode_number, barcode_type='code128', writer_options=None):
    """
    Berilgan raqam uchun shtrix-kod rasmini base64 formatida qaytaradi.
    """
    if writer_options is None:
        # Rasm parametrlarini frontend talabiga moslash mumkin
        writer_options = {
            'module_height': 10.0,
            'module_width': 0.3,
            'font_size': 8,
            'text_distance': 4.0,
            'quiet_zone': 2.0,
            'write_text': True # Raqamni rasmda ko'rsatish/ko'rsatmaslik
        }

    try:
        BARCODE_CLASS = barcode.get_barcode_class(barcode_type)
        # barcode_number ni string ga o'tkazish muhim bo'lishi mumkin
        instance = BARCODE_CLASS(str(barcode_number), writer=ImageWriter())

        buffer = BytesIO()
        # options ni write metodiga uzatish
        instance.write(buffer, options=writer_options)
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        # Data URI formatini qo'shish (frontendda rasm sifatida ishlatish uchun)
        return f"data:image/png;base64,{image_base64}"
    except Exception as e:
        print(f"Error generating barcode image for '{barcode_number}': {e}") # Loglash
        return None