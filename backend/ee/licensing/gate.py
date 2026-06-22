from zane_api.licensing.gate import LicenceFeature
from .models import License


class EELicenseGate:
    """
    License-aware implementation of the core :class:`LicenseGate` seam.

    A feature is unlocked only when a valid license is installed and its tier
    includes that feature (see :meth:`License.is_feature_enabled`).
    """

    def is_feature_enabled(self, feature: LicenceFeature) -> bool:
        installed_license = License.get()
        return installed_license is not None and installed_license.is_feature_enabled(
            feature
        )
