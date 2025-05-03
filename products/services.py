# products/services.py
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
import base64
import random
import string
from .models import Product # Circular import oldini olish uchun funksiya ichida

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