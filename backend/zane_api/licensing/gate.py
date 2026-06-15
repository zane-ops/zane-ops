from typing import Protocol
from enum import StrEnum

# Maximum number of users (members + pending invitations) allowed on the free tier
FREE_USER_LIMIT = 3

# Maximum number of workspaces allowed on the free tier.
FREE_WORKSPACE_LIMIT = 1


class LicenceFeature(StrEnum):
    """
    Catalog of features gated behind a valid paid license.
    The values are user-facing descriptions, the enum keys are what the code uses.
    """

    EXTRA_WORKSPACES = "Extra workspaces"  # more than one workspace
    EXTRA_USER_SEATS = "Extra user seats"  # more than FREE_USER_LIMIT users


class LicenseGate(Protocol):
    """
    Seam between the MIT core and the (optional) commercial EE layer.

    The core ships a free-tier default, the EE app registers a different
    implementation at startup.
    """

    def is_feature_enabled(self, feature: LicenceFeature) -> bool:
        """Whether the given feature is unlocked on this instance."""
        ...


class FreeLicenseGate:
    """
    Free-tier behavior, identical to having no license installed: every
    gated feature is off.
    """

    def is_feature_enabled(self, feature: LicenceFeature) -> bool:
        return False


_gate: LicenseGate = FreeLicenseGate()


def register_license_gate(gate: LicenseGate) -> None:
    global _gate
    _gate = gate


def get_license_gate() -> LicenseGate:
    return _gate


def can_add_user(current_user_count: int) -> tuple[bool, str | None]:
    """
    Whether one more user (member or pending invitation) may be added.

    Returns ``(allowed, error)`` where ``error`` is a user-facing message
    when ``allowed`` is ``False``.
    """
    if current_user_count < FREE_USER_LIMIT:
        return True, None
    if get_license_gate().is_feature_enabled(LicenceFeature.EXTRA_USER_SEATS):
        return True, None
    return False, (
        f"This ZaneOps instance has reached its limit of {FREE_USER_LIMIT} users. "
        "Ask your ZaneOps admin to install or upgrade a license to add more users."
    )


def can_create_workspace(current_workspace_count: int) -> tuple[bool, str | None]:
    """
    Whether an additional workspace may be created.

    Returns ``(allowed, error)`` where ``error`` is a user-facing message
    when ``allowed`` is ``False``.
    """
    if current_workspace_count < FREE_WORKSPACE_LIMIT:
        return True, None
    if get_license_gate().is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES):
        return True, None
    return False, (
        "Creating more than one workspace requires a license. "
        "Please install or upgrade a license that includes this feature."
    )
