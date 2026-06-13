from typing import Dict, List, Self

from django.db import models
from django.conf import settings
from enum import StrEnum
import jwt
from dataclasses import dataclass
from datetime import datetime
from zane_api.utils import Colors
from shortuuid.django_fields import ShortUUIDField


class LicenceFeature(StrEnum):
    UNLIMITED_WORKSPACES = "UNLIMITED_WORKSPACES"


LICENSE_TIERS: Dict[str, List[LicenceFeature]] = {
    "starter": [LicenceFeature.UNLIMITED_WORKSPACES]
}


@dataclass
class LicenseData:
    tier: str
    issued_at: datetime
    expires_at: datetime
    uuid: str
    fingerprint: str

    @classmethod
    def from_dict(cls, data: dict) -> Self:
        return cls(
            tier=data["tier"],
            issued_at=datetime.fromisoformat(data["iat"]),
            expires_at=datetime.fromisoformat(data["exp"]),
            uuid=data["uuid"],
            fingerprint=data["fingerprint"],
        )


class License(models.Model):
    """
    Singleton row holding the raw license key as installed by the user.
    The decoded payload is stored in data but validated against the global public key
    """

    SINGLETON_ID = 1

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

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
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
    def validate_payload(cls, key: str, uuid: str) -> Self | None:
        data: LicenseData | None = None
        try:
            payload = jwt.decode(
                key,
                "public_key.pem",  # TODO: load public key from local path
                algorithms=["RS256"],  # TODO: check the correct algorithm
            )
            data = LicenseData.from_dict(payload)
        except (jwt.InvalidTokenError, KeyError) as e:
            print(f"{Colors.ORANGE}ERROR{Colors.ENDC}: Invalid license: {e}")
        else:
            if data.fingerprint == InstanceMeta.get_fingerprint() and data.uuid == uuid:
                return cls(
                    raw_data=key,
                )

        return None

    def _decode(self):
        data: LicenseData | None = None
        try:
            payload = jwt.decode(
                self.raw_data,
                "public_key.pem",  # TODO: load public key from local path
                algorithms=["RS256"],  # TODO: check the correct algorithm
            )
            data = LicenseData.from_dict(payload)
        except (jwt.InvalidTokenError, KeyError) as e:
            print(f"{Colors.ORANGE}ERROR{Colors.ENDC}: Invalid license: {e}")
        return data

    def __str__(self):
        return f"License(installed_at={self.installed_at})"

    @classmethod
    def get(cls):
        license = cls.objects.filter(id=cls.SINGLETON_ID).first()
        return license

    def is_feature_enabled(self, feature: LicenceFeature):
        try:
            payload = jwt.decode(
                self.raw_data,
                "public_key.pem",  # TODO: load public key from local path
                algorithms=["RS256"],  # TODO: check the correct algorithm
            )
            data = LicenseData.from_dict(payload)
        except (jwt.InvalidTokenError, KeyError) as e:
            print(f"{Colors.ORANGE}ERROR{Colors.ENDC}: Invalid license: {e}")
            return False

        return feature in LICENSE_TIERS.get(data.tier, [])


class InstanceMeta(models.Model):
    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(
        primary_key=True, default=SINGLETON_ID, editable=False
    )

    fingerprint = ShortUUIDField(  # type: ignore
        length=32,
        max_length=255,
        prefix="ist_",
    )

    def save(self, *args, **kwargs):
        self.pk = self.SINGLETON_ID
        super().save(*args, **kwargs)

    @classmethod
    def get_fingerprint(cls):
        settings = cls.objects.filter(pk=cls.SINGLETON_ID).first()
        if settings is None:
            settings = cls.objects.create()

        return settings.fingerprint
