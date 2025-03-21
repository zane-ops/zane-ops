from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.db.models import Q
from . import serializers
from ..models import URL, Deployment, GitDeployment, DeploymentURL


class CertificateCheckSerializer(serializers.Serializer):
    domain = serializers.URLDomainField(required=True)


@extend_schema(exclude=True)
class CheckCertificatesAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "tls_certificates"

    def get(self, request: Request):
        form = CertificateCheckSerializer(
            data=dict(domain=request.query_params.get("domain"))
        )
        if form.is_valid(raise_exception=True):
            domain: str = form.data["domain"]
            if (
                domain == settings.ZANE_APP_DOMAIN
                or domain == f"*.{settings.ROOT_DOMAIN}"
            ):  # These are default certificates for zaneops and subdomains
                return Response({"validated": True}, status=status.HTTP_200_OK)

            domain_parts = domain.split(".")
            domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)
            existing_urls = URL.objects.filter(
                Q(domain=domain) | Q(domain=domain_as_wildcard)
            ).count()

            existing_docker_deployment_urls = DeploymentURL.objects.filter(
                domain=domain
            ).count()
            total_urls = existing_urls + existing_docker_deployment_urls
            if total_urls > 0:
                return Response({"validated": True}, status=status.HTTP_200_OK)
        raise exceptions.PermissionDenied(
            "A certificate cannot be issued for this domain"
        )
