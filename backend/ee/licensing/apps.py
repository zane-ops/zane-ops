from django.apps import AppConfig


class LicensingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ee.licensing"

    def ready(self):
        from zane_api.licensing.gate import register_license_gate
        from .gate import EELicenseGate

        register_license_gate(EELicenseGate())
