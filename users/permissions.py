# users/permissions.py
from rest_framework import permissions

class IsSuperuser(permissions.BasePermission):
    """
    Allows access only to superusers.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)

# Boshqa rollar uchun ham shu yerda permissionlar yaratish mumkin
# class IsStoreAdmin(permissions.BasePermission):
#     def has_permission(self, request, view):
#         return bool(
#             request.user and
#             request.user.is_authenticated and
#             hasattr(request.user, 'profile') and
#             request.user.profile.role and
#             request.user.profile.role.name == 'Admin' # Yoki Role.ADMIN
#         )
    # def has_object_permission(self, request, view, obj):
    #     # Obyekt userning do'koniga tegishlimi?
    #     if isinstance(obj, Store): return obj == request.user.profile.store
    #     if hasattr(obj, 'store'): return obj.store == request.user.profile.store
    #     # Boshqa tekshiruvlar...
    #     return False # Yoki True (agar obyekt tekshiruvi shart bo'lmasa)