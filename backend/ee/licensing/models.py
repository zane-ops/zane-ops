import hashlib

from functools import cached_property
from typing import Dict, List, Self

from django.db import models
from django.conf import settings
from enum import StrEnum
from zane_api.licensing.gate import LicenceFeature
import jwt
from dataclasses import dataclass
from datetime import datetime, timezone
from zane_api.utils import Colors
import uuid
from uuid import UUID


SINGLETON_ID = 1


class LicenseTiers(StrEnum):
    FREE = "free"  # free license, no paid feature enabled
    STARTER = "starter"  # base tier


TIER_MATRIX: Dict[LicenseTiers, List[LicenceFeature]] = {
    LicenseTiers.FREE: [],
    LicenseTiers.STARTER: [
        LicenceFeature.EXTRA_WORKSPACES,
        LicenceFeature.EXTRA_USER_SEATS,
    ],
}


@dataclass
class LicenseData:
    tier: LicenseTiers
    issued_at: datetime
    expires_at: datetime
    # license remote UUID
    uuid: str
    fingerprint: str

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            tier=LicenseTiers(data["tier"]),
            issued_at=datetime.fromtimestamp(data["iat"], tz=timezone.utc),
            expires_at=datetime.fromtimestamp(data["exp"], tz=timezone.utc),
            uuid=data["uuid"],
            fingerprint=data["fingerprint"],
        )


class LicenseError(Exception):
    """
    Raised when a license token cannot be validated.

    The message is user-facing and explains *why* the license was rejected.
    """


class License(models.Model):
    """
    Singleton row holding the raw license key as installed by the user.
    The decoded payload is stored in data but validated against the global public key
    """

    id = models.PositiveSmallIntegerField(
        primary_key=True, default=SINGLETON_ID, editable=False
    )

    raw_data = models.TextField(null=False, blank=False)
    installed_at = models.DateTimeField(auto_now_add=True)
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=SINGLETON_ID),
                name="license_singleton_id",
            ),
        ]

    def save(self, *args, **kwargs):
        self.pk = SINGLETON_ID
        super().save(*args, **kwargs)

    @property
    def is_valid(self) -> bool:
        return self._data is not None

    @property
    def expires_at(self) -> datetime:
        data = self._data
        if not data:
            return datetime.fromtimestamp(0)
        return data.expires_at

    @classmethod
    def validate_payload(cls, key: str, uuid: str | UUID) -> Self:
        """
        Decode and validate a license `key` against this instance.

        Raises `LicenseError` with a user-facing message when the license is
        not acceptable (bad signature, expired, malformed, or bound to another
        instance/license ID).
        """
        data = cls._decode_token(key)

        if data.fingerprint != InstanceMeta.get_fingerprint():
            raise LicenseError(
                "This license key is not bound to this ZaneOps instance."
            )
        if data.uuid != str(uuid):
            raise LicenseError(
                "This license key does not match the provided license ID."
            )

        return cls(raw_data=key)

    @staticmethod
    def _decode_token(key: str) -> LicenseData:
        """
        Decode a raw license `key` with the global public key.

        Raises `LicenseError` describing why the token could not be read:
        expired, invalid/tampered signature, or malformed payload.
        """
        try:
            payload = jwt.decode(
                key, settings.ZANEOPS_LICENSE_PUBLIC_KEY, algorithms=["RS256"]
            )
        except jwt.ExpiredSignatureError:
            raise LicenseError("This license has expired.")
        except jwt.InvalidTokenError:
            raise LicenseError("This license key is invalid or has been tampered with.")

        try:
            return LicenseData.from_dict(payload)
        except (KeyError, ValueError, TypeError):
            raise LicenseError("This license key is malformed.")

    @cached_property
    def _data(self) -> LicenseData | None:
        """
        The decoded payload, or ``None`` (logged) if the license is invalid.

        Memoized per instance: ``raw_data`` is fixed once loaded, so all
        accessors share one RS256 verify. The cache lives only for the
        instance's lifetime, so a fresh request always re-checks ``exp``.

        **Warning**:
            Do not make this a process-wide/TTL cache! That would bypass
            PyJWT's ``exp`` check and serve expired licenses as valid.
        """
        try:
            return self._decode_token(self.raw_data)
        except LicenseError as e:
            print(f"{Colors.ORANGE}ERROR{Colors.ENDC}: Invalid license: {e}")
            return None

    def __str__(self):
        return f"License(installed_at={self.installed_at}, expires_at=installed_at={self.expires_at})"

    @classmethod
    def get(cls):
        return cls.objects.filter(id=SINGLETON_ID).first()

    @classmethod
    async def aget(cls):
        return await cls.objects.filter(id=SINGLETON_ID).afirst()

    @property
    def tier(self) -> LicenseTiers:
        data = self._data
        return data.tier if data is not None else LicenseTiers.FREE

    @property
    def uuid(self) -> str:
        data = self._data
        return data.uuid if data is not None else str(uuid.UUID(int=0))

    def is_feature_enabled(self, feature: LicenceFeature):
        data = self._data
        return data is not None and feature in TIER_MATRIX.get(data.tier, [])


class InstanceMeta(models.Model):
    id = models.PositiveSmallIntegerField(
        primary_key=True, default=SINGLETON_ID, editable=False
    )

    fingerprint = models.TextField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=SINGLETON_ID),
                name="instance_meta_singleton_id",
            ),
        ]

    def save(self, *args, **kwargs):
        self.pk = SINGLETON_ID
        super().save(*args, **kwargs)

    @classmethod
    def _create_fingerprint(cls):
        instance_id = str(uuid.uuid4())
        fingerprint_data = "sha256:" + hashlib.sha256(instance_id.encode()).hexdigest()
        return cls.objects.create(fingerprint=fingerprint_data)

    @classmethod
    def get_fingerprint(cls):
        """
        Return the fingerprint of this ZaneOps instance as `"sha256:<hexdigest>"`.
        The underlying instance id is a UUID persisted in the database and saved as a singleton object in the DB.
        """
        return (
            cls.objects.filter(pk=SINGLETON_ID).first() or cls._create_fingerprint()
        ).fingerprint
