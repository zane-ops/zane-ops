from typing import Protocol

# Maximum number of users (members + pending invitations) allowed on the
# free tier of a ZaneOps instance. EE implementation may lift this
# limit when a valid license is installed.
FREE_USER_LIMIT = 3


class LicenseGate(Protocol):
    """
    Seam between the MIT core and the (optional) commercial EE layer.

    The core ships a free-tier default ; the EE app registers a different
    implementation at startup. Each method returns ``(allowed, error)`` where
    ``error`` is a user-facing message when ``allowed`` is ``False``.
    """

    def can_register_user(self, current_user_count: int) -> tuple[bool, str | None]:
        """Whether a new account may be created by consuming an invitation."""
        ...

    def can_invite_user(self, projected_user_count: int) -> tuple[bool, str | None]:
        """Whether a new invitation may be created (members + invitations)."""
        ...

    def can_create_workspace(self) -> tuple[bool, str | None]:
        """Whether an additional workspace may be created."""
        ...


class FreeLicenseGate:
    """
    Free-tier behavior, identical to having no license installed:
    up to ``FREE_USER_LIMIT`` users and a single workspace.
    """

    def can_register_user(self, current_user_count: int) -> tuple[bool, str | None]:
        if current_user_count < FREE_USER_LIMIT:
            return True, None
        return False, (
            f"This ZaneOps instance has reached its limit of {FREE_USER_LIMIT} users. "
            "Ask your ZaneOps admin to install a license before you can join."
        )

    def can_invite_user(self, projected_user_count: int) -> tuple[bool, str | None]:
        if projected_user_count < FREE_USER_LIMIT:
            return True, None
        return False, (
            f"This ZaneOps instance has reached its limit of {FREE_USER_LIMIT} users. "
            "Ask your ZaneOps admin to install a license to add more users."
        )

    def can_create_workspace(self) -> tuple[bool, str | None]:
        return False, (
            "Creating more than one workspace requires a license. "
            "Please install a license that includes this feature."
        )


_gate: LicenseGate = FreeLicenseGate()


def register_license_gate(gate: LicenseGate) -> None:
    global _gate
    _gate = gate


def get_license_gate() -> LicenseGate:
    return _gate
