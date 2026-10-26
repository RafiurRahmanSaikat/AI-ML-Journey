from rest_framework.permissions import SAFE_METHODS, BasePermission

ADMIN_ROLES = ("super_admin", "headmaster")


def is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in ADMIN_ROLES))


class RoleBasedPermission(BasePermission):
    """Authenticated users read; admins write. Views can set `teacher_can_write = True`."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS or is_admin(user):
            return True
        return bool(getattr(view, "teacher_can_write", False) and user.role == "teacher")
