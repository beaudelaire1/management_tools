from django.http import HttpRequest, HttpResponse
from django.urls import path


def health_view(_: HttpRequest) -> HttpResponse:
    return HttpResponse("organizations-ok", content_type="text/plain")


urlpatterns = [
    path("health/", health_view, name="organizations-health"),
]
