# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Role, UserProfile # Store kerak emas

# UserProfileInline (o'zgarishsiz)
# class UserProfileInline(admin.StackedInline):
#     model = UserProfile
#     can_delete = False
#     verbose_name_plural = 'Profil'
#     fk_name = 'user'
#     # Agar 'store' maydoni ko'rsatilgan bo'lsa, olib tashlang
#     # fields = ('full_name', 'phone_number', 'role', 'salary', 'address', 'salary_status')

# CustomUserAdmin
class CustomUserAdmin(BaseUserAdmin):
    # inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'get_full_name', 'get_role', 'is_staff', 'is_active')
    list_select_related = ('profile', 'profile__role')
    # list_filter dan store olib tashlandi (agar bo'lsa)
    list_filter = ('is_staff', 'is_active', 'profile__role') # Profil roli bo'yicha filtr qolishi mumkin
    search_fields = ('username', 'email', 'profile__full_name', 'profile__phone_number')

    def get_full_name(self, instance):
        # Profil mavjudligini tekshirish
        return instance.profile.full_name if hasattr(instance, 'profile') else '-'
    get_full_name.short_description = 'To\'liq ismi'

    def get_role(self, instance):
        if hasattr(instance, 'profile') and instance.profile.role:
            return instance.profile.role.name
        return None
    get_role.short_description = 'Roli'

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# RoleAdmin (o'zgarishsiz)
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# UserProfileAdmin (agar registratsiya qilingan bo'lsa)
# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'full_name', 'phone_number', 'role') # store olib tashlandi
#     search_fields = ('full_name', 'phone_number', 'user__username')
#     list_filter = ('role',) # store filtri olib tashlandi
#     list_select_related = ('user', 'role')

# StoreAdmin (agar bo'lsa) o'chirildi