from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, exceptions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from django.db.models import Q
from rest_framework import serializers
from ..models import URL
from .serializers import URLDomainField
from django.db import connection
from zane_api.utils import domain_to_wildcard
from container_registry.models import BuildRegistry
from typing import cast


class CertificateCheckSerializer(serializers.Serializer):
    domain = URLDomainField(required=True)


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
            # Check against ZaneOps base domains
            domain: str = cast(dict[str, str], form.data)["domain"].lower()
            if (
                domain == settings.ZANE_APP_DOMAIN
                or domain == f"*.{settings.ROOT_DOMAIN}"
            ):  # These are default certificates for zaneops and subdomains
                return Response({"validated": True}, status=status.HTTP_200_OK)

            # Check for service domains
            domain_as_wildcard = domain_to_wildcard(domain)
            existing_urls = URL.objects.filter(
                Q(domain=domain) | Q(domain=domain_as_wildcard)
            ).exists()

            if existing_urls:
                return Response({"validated": True}, status=status.HTTP_200_OK)

            # Check for build registry urls
            if BuildRegistry.objects.filter(registry_domain=domain).exists():
                return Response({"validated": True}, status=status.HTTP_200_OK)

            # Check compose stack URLs
            # Use PostgreSQL's jsonb_each and jsonb_array_elements to search nested JSON
            # The urls field structure is: {service_name: [{domain, base_path, ...}, ...]}
            query = """
                SELECT cs.id
                FROM compose_composestack cs,
                    jsonb_each(cs.urls) AS services(service_name, routes),
                    jsonb_array_elements(services.routes) AS route
                WHERE cs.urls IS NOT NULL
                AND (
                  lower(route->>'domain') = %s OR lower(route->>'domain') = %s
                )
                LIMIT 1
            """
            params = [
                domain,
                domain_as_wildcard,
            ]
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                result = cursor.fetchone()

            if result:
                return Response({"validated": True}, status=status.HTTP_200_OK)

        raise exceptions.PermissionDenied(
            "A certificate cannot be issued for this domain"
        )
