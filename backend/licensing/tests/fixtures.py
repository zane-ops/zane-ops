import json
import re
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from unittest.mock import patch
from uuid import uuid4

import jwt
import responses
from django.conf import settings
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from rest_framework import status

from ..models import InstanceMeta, LicenseTiers
from zane_api.utils import jprint


class LicenseMockScenario(StrEnum):
    """Remote-API scenarios exercising the edges of `License.validate_payload()`."""

    VALID = "valid"
    NOT_FOUND = "not_found"  # remote returns 404 -> response.raise_for_status() fails
    MALFORMED_RESPONSE = "malformed_response"  # 200 but body is missing "key"
    INVALID_SIGNATURE = "invalid_signature"  # token signed by an untrusted private key
    MALFORMED_TOKEN = "malformed_token"  # valid signature, payload missing a claim
    EXPIRED = "expired"  # token "iat"/"exp" are in the past
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"  # token bound to another instance
    UUID_MISMATCH = "uuid_mismatch"  # token "uuid" != the requested one


def _generate_rsa_keypair() -> tuple[str, str]:
    """Return a `(private_pem, public_pem)` pair for signing/validating tokens."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def mock_remote_api_for_licensing(
    tier: LicenseTiers = LicenseTiers.STARTER,
    scenario: LicenseMockScenario = LicenseMockScenario.VALID,
):
    """
    Mock Remote API for licensing.

    Supported endpoints:
      - GET /api/v1/licenses/<uuid>
          -> returns a license token (`{"key": <jwt>}`) for the requested UUID.

    `scenario` selects which edge of the install flow to exercise (see
    `LicenseMockScenario`). The happy path (`VALID`) signs a token bound to this
    instance's fingerprint and the requested UUID.

    This also mocks the public key from `_load_public_key()`: an ephemeral RSA
    keypair is generated per call, its private half signs the token and its
    public half is patched into the model so `License.validate_payload()` accepts
    it (the bundled `keys/public_key.pem` is ignored). `INVALID_SIGNATURE` signs
    with a *different*, untrusted key.
    """
    base_url = settings.ZANEOPS_REMOTE_API_HOST

    trusted_private_pem, trusted_public_pem = _generate_rsa_keypair()
    untrusted_private_pem, _ = _generate_rsa_keypair()

    # Started patch is torn down by the base test case's `addCleanup(patch.stopall)`.
    patch("licensing.models._load_public_key", return_value=trusted_public_pem).start()

    license_url_pattern = re.compile(
        rf"^{re.escape(base_url)}/api/v1/licenses/(?P<uuid>[^/]+)/?$",
        re.IGNORECASE,
    )

    def get_license_callback(request):
        matched = license_url_pattern.match(request.url)
        license_uuid = matched.group("uuid")  # type: ignore

        if scenario is LicenseMockScenario.NOT_FOUND:
            return (
                status.HTTP_404_NOT_FOUND,
                {},
                json.dumps({"detail": "License not found"}),
            )

        if scenario is LicenseMockScenario.MALFORMED_RESPONSE:
            # 200 OK, but the body does not carry the expected "key" field.
            return (status.HTTP_200_OK, {}, json.dumps({"detail": "ok"}))

        now = datetime.now(timezone.utc)
        payload = {
            "tier": tier.value,
            "iat": now.timestamp(),
            "exp": (now + timedelta(days=365)).timestamp(),
            "uuid": license_uuid,
            "fingerprint": InstanceMeta.get_fingerprint(),
        }
        signing_key = trusted_private_pem

        match scenario:
            case LicenseMockScenario.INVALID_SIGNATURE:
                signing_key = untrusted_private_pem
            case LicenseMockScenario.MALFORMED_TOKEN:
                del payload["uuid"]  # missing claim -> KeyError in from_dict
            case LicenseMockScenario.EXPIRED:
                payload["iat"] = (now - timedelta(days=730)).timestamp()
                payload["exp"] = (now - timedelta(days=365)).timestamp()
            case LicenseMockScenario.FINGERPRINT_MISMATCH:
                payload["fingerprint"] = "sha256:" + "0" * 64
            case LicenseMockScenario.UUID_MISMATCH:
                payload["uuid"] = str(uuid4())

        key = jwt.encode(payload, signing_key, algorithm="RS256")
        return (status.HTTP_200_OK, {}, json.dumps({"key": key}))

    responses.add_callback(
        responses.GET,
        license_url_pattern,
        callback=get_license_callback,
        content_type="application/json",
    )
