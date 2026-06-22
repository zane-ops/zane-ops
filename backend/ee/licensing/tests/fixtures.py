import json
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from unittest import mock
from uuid import uuid4

import jwt
import responses
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from rest_framework import status

from ..constants import ZANEOPS_REMOTE_API_HOST
from ..models import InstanceMeta, LicenseTiers


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

    # unbind-only error cases (remote returns `{code, message}` with 4xx)
    UNBIND_FINGERPRINT_MISMATCH = "unbind_fingerprint_mismatch"
    UNBIND_REBIND_LIMIT = "unbind_rebind_limit"

    # check-only error case (remote returns `{code, message}` with 4xx)
    CHECK_FINGERPRINT_MISMATCH = "check_fingerprint_mismatch"


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


@contextmanager
def mock_remote_api_for_licensing(
    tier: LicenseTiers = LicenseTiers.STARTER,
    scenario: LicenseMockScenario = LicenseMockScenario.VALID,
    fingerprint: str | None = None,
):
    """
    Mock the Remote API for licensing, for use as a context manager.

    Supported endpoints:
      - POST /v1/license/install  { uuid, fingerprint }
          -> returns a license token (`{"key": <jwt>}`) for the requested UUID.
      - POST /v1/license/check  { uuid, fingerprint }
          -> returns `{"status": "active", "expired": bool, "key": <jwt>}`.

    `scenario` selects which edge of the install flow to exercise (see
    `LicenseMockScenario`). The happy path (`VALID`) signs a token bound to this
    instance's fingerprint and the requested UUID.

    `fingerprint` lets the caller pass an already-resolved instance fingerprint,
    so the `responses` callbacks never touch the ORM. The callbacks run on
    whatever thread issued the request; for requests made on the event loop
    (e.g. the `check_license` activity), a sync ORM read would raise
    `SynchronousOnlyOperation`. Sync callers can leave it as `None` (resolved
    lazily); async callers should use `amock_remote_api_for_licensing`, which
    pre-resolves it with `await InstanceMeta.aget_fingerprint()`.

    For the duration of the context, the `ZANEOPS_LICENSE_PUBLIC_KEY` constant
    used by `ee.licensing.models` is patched with an ephemeral public key whose
    matching private key signs the returned token, so
    `License.validate_payload()` accepts it.
    `INVALID_SIGNATURE` signs with a *different*, untrusted key.
    """
    base_url = ZANEOPS_REMOTE_API_HOST

    trusted_private_pem, trusted_public_pem = _generate_rsa_keypair()
    untrusted_private_pem, _ = _generate_rsa_keypair()

    install_url = f"{base_url}/v1/license/install"
    unbind_url = f"{base_url}/v1/license/unbind"
    check_url = f"{base_url}/v1/license/check"

    def build_license_key(license_uuid: str) -> str:
        """Sign a license token for `license_uuid`, mutated per `scenario`."""
        now = datetime.now(timezone.utc)
        payload = {
            "tier": tier.value,
            "iat": now.timestamp(),
            "exp": (now + timedelta(days=365)).timestamp(),
            "uuid": license_uuid,
            "fingerprint": (
                fingerprint
                if fingerprint is not None
                else InstanceMeta.get_fingerprint()
            ),
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

        return jwt.encode(payload, signing_key, algorithm="RS256")

    def get_license_callback(request):
        body = json.loads(request.body)
        license_uuid = body["uuid"]

        if scenario is LicenseMockScenario.NOT_FOUND:
            return (
                status.HTTP_404_NOT_FOUND,
                {},
                json.dumps({"detail": "License not found"}),
            )

        if scenario is LicenseMockScenario.MALFORMED_RESPONSE:
            # 200 OK, but the body does not carry the expected "key" field.
            return (status.HTTP_200_OK, {}, json.dumps({"detail": "ok"}))

        key = build_license_key(license_uuid)
        return (status.HTTP_200_OK, {}, json.dumps({"key": key}))

    responses.add_callback(
        responses.POST,
        install_url,
        callback=get_license_callback,
        content_type="application/json",
    )

    def check_license_callback(request):
        body = json.loads(request.body)
        license_uuid = body["uuid"]

        if scenario is LicenseMockScenario.NOT_FOUND:
            return (
                status.HTTP_404_NOT_FOUND,
                {},
                json.dumps({"detail": "License not found"}),
            )

        if scenario is LicenseMockScenario.MALFORMED_RESPONSE:
            # 200 OK, but the body does not carry the expected "key" field.
            return (status.HTTP_200_OK, {}, json.dumps({"detail": "ok"}))

        if scenario is LicenseMockScenario.CHECK_FINGERPRINT_MISMATCH:
            return (
                status.HTTP_409_CONFLICT,
                {},
                json.dumps(
                    {
                        "code": "fingerprint_mismatch",
                        "message": "fingerprint does not match current binding",
                    }
                ),
            )

        key = build_license_key(license_uuid)
        return (
            status.HTTP_200_OK,
            {},
            json.dumps(
                {
                    "status": "active",
                    "expired": scenario is LicenseMockScenario.EXPIRED,
                    "key": key,
                }
            ),
        )

    responses.add_callback(
        responses.POST,
        check_url,
        callback=check_license_callback,
        content_type="application/json",
    )

    def unbind_license_callback(request):
        match scenario:
            case LicenseMockScenario.UNBIND_FINGERPRINT_MISMATCH:
                return (
                    status.HTTP_409_CONFLICT,
                    {},
                    json.dumps(
                        {
                            "code": "fingerprint_mismatch",
                            "message": "fingerprint does not match current binding",
                        }
                    ),
                )
            case LicenseMockScenario.UNBIND_REBIND_LIMIT:
                return (
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    {},
                    json.dumps(
                        {
                            "code": "rebind_limit",
                            "message": "rebind limit reached; contact support for an override",
                        }
                    ),
                )
        return (status.HTTP_200_OK, {}, json.dumps({"ok": True}))

    responses.add_callback(
        responses.POST,
        unbind_url,
        callback=unbind_license_callback,
        content_type="application/json",
    )

    with mock.patch(
        "ee.licensing.models.ZANEOPS_LICENSE_PUBLIC_KEY", trusted_public_pem
    ):
        yield


@asynccontextmanager
async def amock_remote_api_for_licensing(
    tier: LicenseTiers = LicenseTiers.STARTER,
    scenario: LicenseMockScenario = LicenseMockScenario.VALID,
):
    """
    Async variant of `mock_remote_api_for_licensing` for tests where the mocked
    request is issued on the event loop (e.g. the `check_license` activity).

    The instance fingerprint is resolved up-front with the async ORM helper so
    the (synchronous) `responses` callbacks never touch the ORM.
    """
    fingerprint = await InstanceMeta.aget_fingerprint()
    with mock_remote_api_for_licensing(
        tier=tier, scenario=scenario, fingerprint=fingerprint
    ):
        yield
