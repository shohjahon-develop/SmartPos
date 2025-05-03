# users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Role, UserProfile

# UserProfile ni User admin panelida ko'rsatish uchun
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profil'
    fk_name = 'user'

# Standard UserAdmin ni kengaytirish
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('username', 'email', 'get_full_name', 'get_role', 'is_staff', 'is_active')
    list_select_related = ('profile', 'profile__role') # So'rovni optimallashtirish

    def get_full_name(self, instance):
        return instance.profile.full_name
    get_full_name.short_description = 'To\'liq ismi'

    def get_role(self, instance):
        if instance.profile.role:
            return instance.profile.role.name
        return None
    get_role.short_description = 'Roli'

    # Agar profilni alohida o'zgartirish kerak bo'lsa, fieldset ni moslash mumkin
    # fieldsets = (...)

# Eski UserAdmin ni o'chirib, yangisini registratsiya qilish
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Rollarni admin panelda ko'rsatish
@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# UserProfile ni alohida ham ko'rsatish (ixtiyoriy)
# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'full_name', 'phone_number', 'role')
#     search_fields = ('full_name', 'phone_number', 'user__username')
#     list_select_related = ('user', 'role')