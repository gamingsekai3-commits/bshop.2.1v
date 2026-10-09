from django.apps import AppConfig

from .translations import lazy_t


class StoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'store'
    # Used by the admin breadcrumbs (Home > Store > Products); follows the language button.
    verbose_name = lazy_t('admin_app_store')
