from django.apps import AppConfig


class LicensingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ee.licensing"

    def ready(self):
        from zane_api.licensing.gate import register_license_gate
        from temporal.registry import register_workflows_and_activities
        from .gate import EELicenseGate
        from .schedules import CheckLicenseWorkflow, check_license

        register_license_gate(EELicenseGate())

        # Wire the EE license-check schedule into the Temporal worker through the
        # core seam, so the core never has to import from `ee/`.
        register_workflows_and_activities(
            workflows=[CheckLicenseWorkflow],
            activities=[check_license],
        )
