import hashlib
from pathlib import Path
import traceback
from typing import Dict, List, Self

from django.db import models
from django.conf import settings
from enum import StrEnum
import jwt
from dataclasses import dataclass
from datetime import datetime
from zane_api.utils import Colors
import uuid
from uuid import UUID


_PUBLIC_KEY_PATH = Path(__file__).parent / "keys" / "public_key.pem"


def _load_public_key() -> str:
    with open(_PUBLIC_KEY_PATH) as f:
        return f.read()


SINGLETON_ID = 1


class LicenceFeature(StrEnum):
    UNLIMITED_WORKSPACES = "UNLIMITED_WORKSPACES"


class LicenseTiers(StrEnum):
    FREE = "free"  # free license, no paid feature enabled
    STARTER = "starter"  # base tier


TIER_MATRIX: Dict[str, List[LicenceFeature]] = {
    LicenseTiers.FREE.value: [],
    LicenseTiers.STARTER.value: [LicenceFeature.UNLIMITED_WORKSPACES],
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
            issued_at=datetime.fromtimestamp(data["iat"]),
            expires_at=datetime.fromtimestamp(data["exp"]),
            uuid=data["uuid"],
            fingerprint=data["fingerprint"],
        )


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
        return self._decode() is not None

    @property
    def expires_at(self) -> datetime:
        data = self._decode()
        if not data:
            return datetime.fromtimestamp(0)
        return data.expires_at

    @classmethod
    def validate_payload(cls, key: str, uuid: str | UUID) -> Self | None:
        data: LicenseData | None = None
        try:
            payload = jwt.decode(
                key,
                _load_public_key(),
                algorithms=["RS256"],
            )
            data = LicenseData.from_dict(payload)
        except (jwt.InvalidTokenError, KeyError, ValueError) as e:
            traceback.print_exc()
            print(f"{Colors.ORANGE}ERROR{Colors.ENDC}: Invalid license: {e}")
        else:
            if data.fingerprint == InstanceMeta.get_fingerprint() and data.uuid == str(
                uuid
            ):
                return cls(
                    raw_data=key,
                )

        return None

    def _decode(self):
        data: LicenseData | None = None
        try:
            payload = jwt.decode(
                self.raw_data,
                _load_public_key(),
                algorithms=["RS256"],
            )
            data = LicenseData.from_dict(payload)
        except (jwt.InvalidTokenError, KeyError, ValueError) as e:
            traceback.print_exc()
            print(f"{Colors.ORANGE}ERROR{Colors.ENDC}: Invalid license: {e}")
        return data

    def __str__(self):
        return f"License(installed_at={self.installed_at})"

    @classmethod
    def get(cls):
        return cls.objects.filter(id=SINGLETON_ID).first()

    @classmethod
    async def aget(cls):
        return await cls.objects.filter(id=SINGLETON_ID).afirst()

    @property
    def tier(self) -> LicenseTiers:
        data = self._decode()
        return data.tier if data is not None else LicenseTiers.FREE

    def is_feature_enabled(self, feature: LicenceFeature):
        data = self._decode()
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
