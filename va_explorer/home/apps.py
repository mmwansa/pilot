from django.apps import AppConfig


class HomeConfig(AppConfig):
    name = "va_explorer.home"

    def ready(self):
        from va_explorer.home import signals  # noqa: F401
