from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # Adjust to match wherever this app actually lives in your tree -
    # judging by "from apps.cart.services import ..." in views.py, that's
    # probably 'apps.accounts'.
    name = 'apps.accounts'

    def ready(self):
        import apps.accounts.signals  # noqa: F401