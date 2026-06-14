from typing import cast

import requests
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status, exceptions
from rest_framework.generics import ListAPIView, DestroyAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from zane_api.permissions import IsInstanceOwner
from zane_api.views.base import BadRequest, DefaultPageNumberPagination

from .models import License, LicenseError
from .serializers import (
    LicenseInstallRemoteResponseSerializer,
    LicenseInstallRequestSerializer,
    LicenseSerializer,
)
from django.db import transaction


class LicenseListAPIView(ListAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = LicenseSerializer
    pagination_class = DefaultPageNumberPagination
    queryset = License.objects.all()


class LicenseUninstallAPIView(DestroyAPIView):
    permission_classes = [IsInstanceOwner]
    queryset = License.objects.all()

    def get_object(self):  # type: ignore
        installed_license = License.get()
        if installed_license is None:
            raise exceptions.NotFound("No license installed in this ZaneOps instance.")
        return installed_license


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

        url = f"{settings.ZANEOPS_REMOTE_API_HOST}/api/v1/licenses/{license_uuid}"
        try:
            response = requests.get(url=url)
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

        serializer = LicenseSerializer(license)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
