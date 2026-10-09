from django.apps import AppConfig

from store.translations import lazy_t


class CartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cart'
    # Used by the admin breadcrumbs (Home > Cart > Orders); follows the language button.
    verbose_name = lazy_t('admin_app_cart')
