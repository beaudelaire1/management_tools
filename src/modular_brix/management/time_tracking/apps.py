from django.apps import AppConfig


class TimeTrackingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modular_brix.management.time_tracking"
    label = "management_time"
