from django.apps import AppConfig


class DeliveryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'delivery'
    verbose_name = 'Хүргэлт'

    def ready(self):
        from . import signals  # noqa: F401  (connects Order -> Delivery)
