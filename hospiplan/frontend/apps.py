from django.apps import AppConfig


class FrontendConfig(AppConfig):
    name = 'frontend'

    def ready(self):
        from . import signals  # noqa: F401  (enregistre les signaux)
