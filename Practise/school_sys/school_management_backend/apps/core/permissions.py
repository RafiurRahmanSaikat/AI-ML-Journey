from rest_framework.permissions import BasePermission, SAFE_METHODS
class AdminOrHeadmaster(BasePermission):
    """Only staff users in Admin or Headmaster group can mutate school data."""
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return u.is_superuser or u.groups.filter(name__in=["Admin", "Headmaster"]).exists()
