from backend.bootstrap import register_zaneops_app_on_proxy
from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import serializers
from ..models import URL, DockerDeployment, GitDeployment


@extend_schema(exclude=True)
class RegisterZaneProxyAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request):
        register_zaneops_app_on_proxy(
            proxy_url=settings.CADDY_PROXY_ADMIN_HOST,
            zane_app_domain=settings.ZANE_APP_DOMAIN,
            zane_api_internal_domain=settings.ZANE_API_SERVICE_INTERNAL_DOMAIN,
            zane_front_internal_domain=settings.ZANE_FRONT_SERVICE_INTERNAL_DOMAIN,
        )
        return Response(data={"success": True}, status=status.HTTP_200_OK)


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

            existing_urls = URL.objects.filter(domain=domain).count()
            existing_docker_deployment_urls = DockerDeployment.objects.filter(
                url=domain
            ).count()
            existing_git_deployment_urls = GitDeployment.objects.filter(
                url=domain
            ).count()
            total_urls = (
                existing_urls
                + existing_docker_deployment_urls
                + existing_git_deployment_urls
            )
            if total_urls > 0:
                return Response({"validated": True}, status=status.HTTP_200_OK)
        raise exceptions.PermissionDenied(
            "A certificate cannot be issued for this domain"
        )
