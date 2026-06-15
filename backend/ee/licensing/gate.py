from zane_api.licensing.gate import (
    FreeLicenseGate,
    FREE_USER_LIMIT,
)
from .models import License, LicenceFeature


class EELicenseGate(FreeLicenseGate):
    """
    License-aware implementation of the core :class:`LicenseGate` seam.

    Below ``FREE_USER_LIMIT`` (and for the first workspace) behavior matches
    the free tier ; beyond it, an installed license enabling the relevant
    feature is required.
    """

    def can_register_user(self, current_user_count: int) -> tuple[bool, str | None]:
        if current_user_count < FREE_USER_LIMIT:
            return True, None

        installed_license = License.get()
        if installed_license is None:
            return False, (
                f"This ZaneOps instance has reached its limit of {FREE_USER_LIMIT} users. "
                "Ask your ZaneOps admin to install a license before you can join."
            )
        if not installed_license.is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES):
            return False, (
                f"This ZaneOps instance has reached the limit of {FREE_USER_LIMIT} users allowed by its current license plan. "
                "Ask your ZaneOps admin to upgrade the license before you can join."
            )
        return True, None

    def can_invite_user(self, projected_user_count: int) -> tuple[bool, str | None]:
        if projected_user_count < FREE_USER_LIMIT:
            return True, None

        installed_license = License.get()
        if installed_license is None:
            return False, (
                f"This ZaneOps instance has reached its limit of {FREE_USER_LIMIT} users. "
                "Ask your ZaneOps admin to install a license to add more users."
            )
        if not installed_license.is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES):
            return False, (
                f"This ZaneOps instance has reached the limit of {FREE_USER_LIMIT} users allowed by its current license plan. "
                "Ask your ZaneOps admin to upgrade the license to add more users."
            )
        return True, None

    def can_create_workspace(self) -> tuple[bool, str | None]:
        installed_license = License.get()
        if installed_license is None:
            return False, (
                "Creating more than one workspace requires a license. "
                "Please install a license that includes this feature."
            )
        if not installed_license.is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES):
            return False, (
                "Your current license plan doesn't include this feature, "
                "so you can only have one workspace. Please upgrade your license to create more."
            )
        return True, None
