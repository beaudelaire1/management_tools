from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("org/", include("modular_brix.foundation.organizations.urls")),
]
