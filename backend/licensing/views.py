from typing import cast

from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from .serializers import (
    LicenseSerializer,
    LicenseInstallRequestSerializer,
    LicenseInstallRemoteResponseSerializer,
)
from rest_framework import status
from django.conf import settings
import requests
from .models import License
from zane_api.views.base import BadRequest
import traceback


class LicenseInstallAPIView(APIView):
    @extend_schema(
        operation_id="licenseInstall",
        request=LicenseInstallRequestSerializer,
        responses={201: LicenseSerializer},
    )
    def post(self, request: Request):
        form = LicenseInstallRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        try:
            url = f"{settings.ZANEOPS_REMOTE_API_HOST}/api/v1/licenses/get"
            response = requests.post(url=url, json=data)
            response.raise_for_status()
            response_form = LicenseInstallRemoteResponseSerializer(data=response.json())
            response_form.is_valid(raise_exception=True)
        except Exception:
            traceback.print_exc()
            raise BadRequest("Invalid license")

        response_data = cast(dict, response_form.validated_data)

        license = License.validate_payload(response_data["key"], data["uuid"])

        if not license:
            raise BadRequest("Invalid license")

        license.save()

        serializer = LicenseSerializer(license)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
