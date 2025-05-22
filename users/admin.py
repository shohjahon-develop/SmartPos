# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Role, UserProfile

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Foydalanuvchi Profili'
    fk_name = 'user'
    # YANGI QO'SHILDI: salary_payment_date
    fields = ('full_name', 'phone_number', 'role', 'salary', 'address', 'salary_payment_date', 'salary_status')
    max_num = 1
    # min_num = 1 # Signal profilni yaratganligi uchun bu shart emas


class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('username', 'email', 'get_full_name', 'get_role', 'is_staff', 'is_active')
    list_select_related = ('profile', 'profile__role') # So'rovni optimallashtirish

    def get_full_name(self, instance):
        if hasattr(instance, 'profile'):
            return instance.profile.full_name
        return '-'
    get_full_name.short_description = 'To\'liq ismi'

    def get_role(self, instance):
        if hasattr(instance, 'profile') and instance.profile.role:
            return instance.profile.role.name
        return None
    get_role.short_description = 'Roli'

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)






# # users/admin.py
# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from django.contrib.auth.models import User
# from .models import Role, UserProfile
#
# # UserProfile ni User admin panelida ko'rsatish uchun
# class UserProfileInline(admin.StackedInline): # Yoki admin.TabularInline
#     model = UserProfile
#     can_delete = False # User o'chirilganda profil ham o'chadi, bu yerda taqiqlash shart emas
#     verbose_name_plural = 'Foydalanuvchi Profili'
#     fk_name = 'user'
#     # Inline da ko'rinadigan va tahrirlanadigan maydonlar
#     # Agar bu yerda bo'sh qoldirsangiz, UserProfile modelidagi hamma tahrirlanadigan maydonlar chiqadi
#     fields = ('full_name', 'phone_number', 'role', 'salary', 'address', 'salary_status') # Misol, o'zingizga moslang
#     # Agar UserProfile yaratilmagan bo'lsa, nechta bo'sh forma ko'rsatish kerak
#     # Yangi user yaratilganda profilni ham to'ldirish uchun `max_num = 1` va `min_num = 1`
#     # yoki `extra = 1` (lekin mavjud userlarda ham qo'shimcha forma chiqadi)
#     # Eng yaxshisi, signal profilni avtomatik yaratganidan keyin tahrirlash
#     max_num = 1 # Faqat bitta profil bo'lishi mumkin (OneToOne)
#     min_num = 1 # Yangi user yaratganda ham profil formasi chiqishi uchun
#
#
# # Standard UserAdmin ni kengaytirish
# class CustomUserAdmin(BaseUserAdmin):
#     inlines = (UserProfileInline, )
#     list_display = ('username', 'email', 'get_full_name', 'get_role', 'is_staff', 'is_active')
#     list_select_related = ('profile', 'profile__role') # So'rovni optimallashtirish
#
#     def get_full_name(self, instance):
#         if hasattr(instance, 'profile'): # Profil mavjudligini tekshirish
#             return instance.profile.full_name
#         return '-' # Agar profil yo'q bo'lsa
#     get_full_name.short_description = 'To\'liq ismi'
#
#     def get_role(self, instance):
#         if hasattr(instance, 'profile') and instance.profile.role: # Profil va rol mavjudligini tekshirish
#             return instance.profile.role.name
#         return None
#     get_role.short_description = 'Roli'
#
#     # User yaratish/tahrirlash formasida UserProfile maydonlarini ham ko'rsatish uchun
#     # fieldsets ga UserProfile maydonlarini qo'shish murakkabroq, inline yaxshiroq.
#
#     # Yangi foydalanuvchi yaratilganda UserProfile avtomatik yaratilishi uchun signal
#     # users/models.py dagi @receiver(post_save, sender=User) allaqachon bu vazifani bajaradi.
#     # Shu signal tufayli UserProfileInline da min_num=1 kerak bo'lmasligi ham mumkin,
#     # chunki User saqlangandan keyin profil yaratiladi va keyingi tahrirlashda ko'rinadi.
#
# # Eski UserAdmin ni o'chirib, yangisini registratsiya qilish
# admin.site.unregister(User)
# admin.site.register(User, CustomUserAdmin)
#
# # Rollarni admin panelda ko'rsatish
# @admin.register(Role)
# class RoleAdmin(admin.ModelAdmin):
#     list_display = ('name', 'description')
#     search_fields = ('name',)
#
# # UserProfile ni alohida ham ko'rsatish (ixtiyoriy, tekshirish uchun qulay)
# # @admin.register(UserProfile)
# # class UserProfileAdmin(admin.ModelAdmin):
# #     list_display = ('user', 'full_name', 'phone_number', 'role')
# #     search_fields = ('full_name', 'phone_number', 'user__username')
# #     list_select_related = ('user', 'role')
#
#
#
#
# # # users/admin.py
# # from django.contrib import admin
# # from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# # from django.contrib.auth.models import User
# # from .models import Role, UserProfile # Store kerak emas
# #
# # # UserProfileInline (o'zgarishsiz)
# # # class UserProfileInline(admin.StackedInline):
# # #     model = UserProfile
# # #     can_delete = False
# # #     verbose_name_plural = 'Profil'
# # #     fk_name = 'user'
# # #     # Agar 'store' maydoni ko'rsatilgan bo'lsa, olib tashlang
# # #     # fields = ('full_name', 'phone_number', 'role', 'salary', 'address', 'salary_status')
# #
# # # CustomUserAdmin
# # class CustomUserAdmin(BaseUserAdmin):
# #     # inlines = (UserProfileInline,)
# #     list_display = ('username', 'email', 'get_full_name', 'get_role', 'is_staff', 'is_active')
# #     list_select_related = ('profile', 'profile__role')
# #     # list_filter dan store olib tashlandi (agar bo'lsa)
# #     list_filter = ('is_staff', 'is_active', 'profile__role') # Profil roli bo'yicha filtr qolishi mumkin
# #     search_fields = ('username', 'email', 'profile__full_name', 'profile__phone_number')
# #
# #     def get_full_name(self, instance):
# #         # Profil mavjudligini tekshirish
# #         return instance.profile.full_name if hasattr(instance, 'profile') else '-'
# #     get_full_name.short_description = 'To\'liq ismi'
# #
# #     def get_role(self, instance):
# #         if hasattr(instance, 'profile') and instance.profile.role:
# #             return instance.profile.role.name
# #         return None
# #     get_role.short_description = 'Roli'
# #
# # admin.site.unregister(User)
# # admin.site.register(User, CustomUserAdmin)
# #
# # # RoleAdmin (o'zgarishsiz)
# # @admin.register(Role)
# # class RoleAdmin(admin.ModelAdmin):
# #     list_display = ('name', 'description')
# #     search_fields = ('name',)
# #
