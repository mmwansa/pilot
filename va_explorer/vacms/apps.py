from django.apps import AppConfig


class VacmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "va_explorer.vacms"

    def ready(self):
        from . import signals  # noqa: F401
