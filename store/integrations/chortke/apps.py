from django.apps import AppConfig


class ChortkeIntegrationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "store.integrations.chortke"
    label = "chortke_integration"
    verbose_name = "اتصال حسابداری چرتکه"
