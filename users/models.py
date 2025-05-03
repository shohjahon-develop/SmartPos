# users/models.py


from django.conf import settings
from django.contrib.auth.models import User
from django.db import models

from subscriptions.models import SubscriptionPlan


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


class Store(models.Model):
    """Har bir alohida do'kon (tenant)"""
    name = models.CharField(max_length=255, verbose_name="Do'kon nomi")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='owned_stores', on_delete=models.PROTECT, verbose_name="Do'kon Egasi") # Do'kon egasi (Admin)
    subscription_plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,  # Tarif o'chirilganda do'konlar qolishi kerak
        null=True,  # Bepul yoki plansiz bo'lishi mumkin
        blank=True,
        related_name='stores',
        verbose_name="Obuna Tarifi"
    )  # CharField o'rniga ForeignKey
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Amal qilish muddati")
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Do'kon"
        verbose_name_plural = "Do'konlar"
        ordering = ['name']

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Foydalanuvchining qo'shimcha ma'lumotlari"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='user_profiles', null=True, blank=True, verbose_name="Do'kon") # YANGI FIELD
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    phone_number = models.CharField(max_length=20, unique=True, blank=True, null=True, verbose_name="Telefon raqami")
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='users', verbose_name="Roli")
    # Frontendda ko'rilgan qo'shimcha maydonlar uchun joy (keyin qo'shamiz)
    salary = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Oylik Maosh (UZS)")
    address = models.TextField(blank=True, null=True, verbose_name="Manzil")
    salary_status_choices = [('Paid', 'Berilgan'), ('Pending', 'Kutilmoqda')] # Masalan
    salary_status = models.CharField(max_length=10, choices=salary_status_choices, null=True, blank=True, verbose_name="Oylik Holati")

    def __str__(self):
        store_name = f" ({self.store.name})" if self.store else ""
        return f"{self.user.username} profili{store_name}"

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

