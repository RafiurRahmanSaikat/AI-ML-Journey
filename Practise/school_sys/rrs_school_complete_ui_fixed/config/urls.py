from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from school.frontend import dashboard

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
    path("api/", include("school.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
