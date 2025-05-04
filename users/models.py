# users/models.py


from django.conf import settings
from django.contrib.auth.models import User
from django.db import models




class Role(models.Model):
    """Foydalanuvchi Rollari (masalan, Sotuvchi, Omborchi, Administrator)"""
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True) # Rol haqida qisqacha izoh

    # Ruxsatlar (Permissions) Django ning o'rnatilgan tizimi orqali bog'lanadi
    # Yoki keyinchalik maxsus ruxsatlar qo'shish mumkin

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Rollar"




class UserProfile(models.Model):
    """Foydalanuvchining qo'shimcha ma'lumotlari"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Telefon raqami")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name="Roli")
    # Frontendda ko'rilgan qo'shimcha maydonlar uchun joy (keyin qo'shamiz)
    salary = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Oylik Maosh (UZS)")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil")
    salary_status_choices = [('Paid', 'Berilgan'), ('Pending', 'Kutilmoqda')] # Masalan
    salary_status = models.CharField(max_length=10, choices=salary_status_choices, null=True, blank=True, verbose_name="Oylik Holati")

    def __str__(self):
        return f"{self.user.username} "

    class Meta:
        verbose_name = "Foydalanuvchi Profili"
        verbose_name_plural = "Foydalanuvchi Profillari"

# Django User modeliga signal orqali avtomatik UserProfile yaratish (ixtiyoriy, lekin qulay)
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Yangi User yaratilganda unga bog'liq UserProfile yaratadi yoki mavjudini yangilaydi.
    """
    if created:
        UserProfile.objects.create(user=instance)
    # Agar user ma'lumotlari yangilansa, profilni ham yangilash kerak bo'lishi mumkin
    # instance.profile.save() # Bu yerda qo'shimcha logika bo'lishi mumkin

