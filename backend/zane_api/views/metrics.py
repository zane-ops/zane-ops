from typing import Literal
from drf_spectacular.utils import extend_schema
from rest_framework import status, exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ServiceMetricsQuery, ServiceMetricsResponseSerializer
from ..models import (
    Project,
    Service,
    ServiceMetrics,
    Deployment,
    Environment,
)
from django.utils import timezone
from datetime import timedelta

from django.db.models import (
    Avg,
    Sum,
    F,
    Func,
    Value,
    DateTimeField,
)


# Define a custom function to extract epoch seconds from a datetime.
class ExtractEpoch(Func):
    function = "EXTRACT"
    template = "%(function)s(EPOCH FROM %(expressions)s)"


class ServiceMetricsAPIView(APIView):
    serializer_class = ServiceMetricsResponseSerializer

    @extend_schema(
        parameters=[ServiceMetricsQuery],
        summary="Get service or deployment metrics",
    )
    def get(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug=Environment.PRODUCTION_ENV_NAME,
        deployment_hash: str | None = None,
    ):
        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = Service.objects.get(
                slug=service_slug, project=project, environment=environment
            )
            deployment = None
            if deployment_hash is not None:
                deployment = Deployment.objects.get(
                    hash=deployment_hash,
                    service=service,
                )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist."
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}` does not exist in this project."
            )
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist in this service."
            )
        else:
            form = ServiceMetricsQuery(data=request.query_params)
            if form.is_valid(raise_exception=True):
                time_range: Literal[
                    "LAST_HOUR", "LAST_6HOURS", "LAST_DAY", "LAST_WEEK", "LAST_MONTH"
                ] = form.validated_data.get("time_range")  # type: ignore

                now = timezone.now()
                qs = ServiceMetrics.objects.filter(service=service)
                if deployment is not None:
                    qs = qs.filter(deployment=deployment)

                match time_range:
                    case "LAST_HOUR":
                        start_time = now - timedelta(hours=1)
                        interval = "30 seconds"
                    case "LAST_6HOURS":
                        start_time = now - timedelta(hours=6)
                        interval = "5 minutes"
                    case "LAST_DAY":
                        start_time = now - timedelta(hours=24)
                        interval = "15 minutes"
                    case "LAST_WEEK":
                        start_time = now - timedelta(days=7)
                        interval = "1 hours"
                    case "LAST_MONTH":
                        start_time = now - timedelta(days=30)
                        interval = "1 days"
                    case _:
                        raise NotImplementedError("This should be unreachable")

                qs = qs.filter(
                    created_at__gte=start_time,
                )

                """
                The general algorithm is like this :
                - group all queries by intervals, with the `start_time` of the interval (called bucket_epoch underneath)
                - then get the average of the cpu/mem and sum of network/disk in these intervals 
                """
                qs = qs.annotate(
                    bucket_epoch=Func(
                        # from the docs :
                        #  - https://database.guide/postgresql-date_bin-function-explained/
                        #  - https://www.postgresql.org/docs/current/functions-datetime.html#FUNCTIONS-DATETIME-BIN
                        # In PostgreSQL, the DATE_BIN() function enables us to “bin” a timestamp into a given interval aligned with a specific origin.
                        # In other words, we can use this function to map (or force) a timestamp to the nearest specified interval.
                        Value(interval),
                        F("created_at"),
                        Value("2000-01-01"),
                        function="DATE_BIN",
                        output_field=DateTimeField(),
                    )
                )

                # Group by bucket_epoch and aggregate metrics.
                aggregated = (
                    qs.values("bucket_epoch")
                    .annotate(
                        avg_cpu=Avg("cpu_percent"),
                        avg_memory=Avg("memory_bytes"),
                        total_net_tx=Sum("net_tx_bytes"),
                        total_net_rx=Sum("net_rx_bytes"),
                        total_disk_read=Sum("disk_read_bytes"),
                        total_disk_write=Sum("disk_writes_bytes"),
                    )
                    .order_by("bucket_epoch")
                )

                serializer = ServiceMetricsResponseSerializer(aggregated)
                return Response(data=serializer.data, status=status.HTTP_200_OK)
