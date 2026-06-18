from temporalio import workflow, activity

with workflow.unsafe.imports_passed_through():
    import requests
    from asgiref.sync import sync_to_async
    from ..constants import ZANEOPS_REMOTE_API_HOST
    from ..models import License, LicenseError, InstanceMeta


@activity.defn
async def check_license(license_uuid: str) -> str:
    """
    Re-validate the installed license against the remote API.

    Returns one of:
      - ``"no_license"``  : nothing is installed, nothing to do.
      - ``"valid"``       : the license is still valid; its key was refreshed.
      - ``"removed"``     : the license is no longer valid for this instance
                            (expired, rebound elsewhere, fingerprint mismatch,
                            …) and has been uninstalled locally.
      - ``"unreachable"`` : the license server could not be reached; the license
                            is kept as-is and re-checked on the next run.
    """
    installed = await License.aget()
    if installed is None:
        return "no_license"

    fingerprint = await InstanceMeta.aget_fingerprint()
    url = f"{ZANEOPS_REMOTE_API_HOST}/v1/license/check"
    try:
        response = requests.post(
            url=url,
            json={
                "uuid": str(installed.uuid),
                "fingerprint": fingerprint,
            },
        )
        response.raise_for_status()
    except requests.HTTPError as e:
        if e.response is not None and 399 < e.response.status_code < 500:
            # The license is no longer bound to this instance (not found,
            # fingerprint mismatch, …) -> uninstall it locally.
            await installed.adelete()
            return "removed"
        # Transient server error -> keep the license and let Temporal retry.
        raise
    except requests.RequestException:
        # Network error -> keep the license, re-check on the next run.
        return "unreachable"

    try:
        payload = response.json()
    except ValueError:
        return "unreachable"

    key = payload.get("key")
    if payload.get("expired") or not key:
        await installed.adelete()
        return "removed"

    try:
        refreshed = await License.avalidate_payload(key, installed.uuid)
    except LicenseError:
        await installed.adelete()
        return "removed"

    # Update the existing row
    installed.raw_data = refreshed.raw_data
    await installed.asave()
    return "valid"
