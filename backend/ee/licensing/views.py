from typing import cast

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status, exceptions
from rest_framework.generics import RetrieveAPIView, DestroyAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from temporalio.service import RPCError
from zane_api.permissions import IsInstanceOwner
from zane_api.views.base import BadRequest
from asgiref.sync import async_to_sync

from temporal.client import TemporalClient
from .constants import (
    ZANEOPS_REMOTE_API_HOST,
    LICENSE_CHECK_SCHEDULE_ID,
    LICENSE_CHECK_INTERVAL,
)
from .models import License, LicenseError, InstanceMeta
from .schedules import CheckLicenseWorkflow
from .serializers import (
    LicenseInstallRemoteResponseSerializer,
    LicenseUninstallRemoteErrorResponseSerializer,
    LicenseInstallRequestSerializer,
    LicenseSerializer,
)
from django.db import transaction


class LicenseDetailsAPIView(RetrieveAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = LicenseSerializer
    queryset = License.objects.all()

    def get_object(self):  # type: ignore
        installed_license = License.get()
        if installed_license is None:
            raise exceptions.NotFound("No license installed in this ZaneOps instance.")
        return installed_license


class LicenseUninstallAPIView(DestroyAPIView):
    permission_classes = [IsInstanceOwner]
    queryset = License.objects.all()

    def get_object(self):  # type: ignore
        installed_license = License.get()
        if installed_license is None:
            raise exceptions.NotFound("No license installed in this ZaneOps instance.")
        return installed_license

    @transaction.atomic()
    def perform_destroy(self, instance: License):
        url = f"{ZANEOPS_REMOTE_API_HOST}/v1/license/unbind"

        data = {
            "uuid": str(instance.uuid),
            "fingerprint": InstanceMeta.get_fingerprint(),
        }
        print(f"{data=}")
        try:
            response = requests.post(
                url=url,
                json=data,
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            if e.response is not None:
                if e.response.status_code == status.HTTP_404_NOT_FOUND:
                    raise BadRequest(
                        f"No license was found for the ID `{str(instance.uuid)}`."
                    )
                elif 399 < e.response.status_code < 500:
                    try:
                        form = LicenseUninstallRemoteErrorResponseSerializer(
                            data=e.response.json()
                        )
                    except Exception:
                        print("Validation error")
                    else:
                        if form.is_valid():
                            data = cast(dict, form.validated_data)
                            raise BadRequest(
                                f"Received error from the remote API: {data['message']}"
                            )

            raise BadRequest(
                "The license server returned an unexpected error, please try again later."
            )
        except requests.RequestException:
            raise BadRequest(
                "Could not reach the license server, please check your connection and try again."
            )

        def commit_callback():
            """Remove the recurring license-check schedule, if any."""
            try:
                async_to_sync(TemporalClient.adelete_schedule)(
                    LICENSE_CHECK_SCHEDULE_ID
                )

            except RPCError:
                # already gone
                pass

        transaction.on_commit(commit_callback)

        super().perform_destroy(instance)

    @extend_schema(
        responses={204: None},
        operation_id="uninstallLicense",
        summary="Delete installed license from this instance.",
    )
    def delete(self, request: Request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class LicenseInstallAPIView(APIView):
    permission_classes = [IsInstanceOwner]

    @transaction.atomic()
    @extend_schema(
        operation_id="licenseInstall",
        request=LicenseInstallRequestSerializer,
        responses={201: LicenseSerializer},
    )
    def post(self, request: Request):
        form = LicenseInstallRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)
        license_uuid = data["uuid"]

        url = f"{ZANEOPS_REMOTE_API_HOST}/v1/license/install"
        try:
            response = requests.post(
                url=url,
                json={
                    "uuid": str(license_uuid),
                    "fingerprint": InstanceMeta.get_fingerprint(),
                },
            )
            response.raise_for_status()
        except requests.HTTPError as e:
            if (
                e.response is not None
                and e.response.status_code == status.HTTP_404_NOT_FOUND
            ):
                raise BadRequest(f"No license was found for the ID `{license_uuid}`.")
            raise BadRequest(
                "The license server returned an unexpected error, please try again later."
            )
        except requests.RequestException:
            raise BadRequest(
                "Could not reach the license server, please check your connection and try again."
            )

        try:
            payload = response.json()
        except ValueError:
            raise BadRequest("Received an invalid response from the license server.")

        response_form = LicenseInstallRemoteResponseSerializer(data=payload)
        if not response_form.is_valid():
            raise BadRequest("Received an invalid response from the license server.")

        response_data = cast(dict, response_form.validated_data)

        try:
            license = License.validate_payload(response_data["key"], license_uuid)
        except LicenseError as e:
            raise BadRequest(str(e))

        existing_license = License.get()

        if existing_license:
            existing_license.delete()

        license.installed_by = request.user
        license.save()

        def commit_callback():
            """
            (Re)create the recurring license-check schedule, bound to `license_uuid`.

            Any stale schedule is removed first so a re-install (potentially with a new
            license id) replaces the previous one.
            """

            try:
                TemporalClient.delete_schedule(LICENSE_CHECK_SCHEDULE_ID)
            except RPCError:
                # nothing to replace yet
                pass

            async_to_sync(TemporalClient.acreate_schedule)(
                workflow=CheckLicenseWorkflow.run,
                args=str(license_uuid),
                id=LICENSE_CHECK_SCHEDULE_ID,
                interval=LICENSE_CHECK_INTERVAL,
                task_queue=settings.TEMPORALIO_SCHEDULE_TASK_QUEUE,
            )

        transaction.on_commit(commit_callback)

        serializer = LicenseSerializer(license)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
