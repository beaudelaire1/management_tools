from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("app/", include("modular_brix.portal.urls")),
    path("org/", include("modular_brix.foundation.organizations.urls")),
]
