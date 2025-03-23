from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.request import Request

from ..utils import generate_random_chars
from ..serializers import ServiceDeploymentSerializer, ServiceSerializer
from ..models import (
    Service,
    Project,
    Deployment,
    DeploymentChange,
    DeploymentURL,
    Environment,
)
from django.db.models import Q
import django.db.transaction as transaction
from .serializers import DockerServiceWebhookDeployRequestSerializer
from ..temporal.shared import DeploymentDetails
from ..temporal.main import start_workflow
from ..temporal.workflows import DeployDockerServiceWorkflow


class RegenerateServiceDeployTokenAPIView(APIView):
    serializer_class = ServiceSerializer

    @extend_schema(
        summary="Regenerate service deploy token",
        operation_id="regenerateServiceDeployToken",
    )
    def patch(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )

        service = (
            Service.objects.filter(
                Q(slug=service_slug) & Q(project=project) & Q(environment=environment)
            )
            .select_related("project", "healthcheck", "environment")
            .prefetch_related("volumes", "ports", "urls", "env_variables")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        service.deploy_token = generate_random_chars(20)
        service.save()

        response = ServiceSerializer(service)
        return Response(response.data)


class WebhookDeployServiceAPIView(APIView):
    serializer_class = ServiceDeploymentSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "deploy_webhook"

    @transaction.atomic()
    @extend_schema(
        request=DockerServiceWebhookDeployRequestSerializer,
        operation_id="webhookDeployService",
        summary="Webhook to deploy a docker service",
        description="trigger a new deployment.",
    )
    def put(self, request: Request, deploy_token: str):

        service = (
            Service.objects.filter(deploy_token=deploy_token)
            .select_related("project", "healthcheck", "environment")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with a deploy_token `{deploy_token}` doesn't exist."
            )

        form = DockerServiceWebhookDeployRequestSerializer(
            data=request.data if request.data is not None else {},
            context={"service": service},
        )
        if form.is_valid(raise_exception=True):
            new_image = form.data.get("new_image")  # type: ignore

            if new_image is not None:
                service.add_change(
                    DeploymentChange(
                        type=DeploymentChange.ChangeType.UPDATE,
                        field=DeploymentChange.ChangeField.SOURCE,
                        old_value={
                            "image": service.image,
                            "credentials": service.credentials,
                        },
                        new_value={
                            "image": new_image,
                            "credentials": service.credentials,
                        },
                        service=service,
                    )
                )

            commit_message = form.data.get("commit_message")  # type: ignore
            new_deployment = Deployment.objects.create(
                service=service,
                commit_message=commit_message if commit_message else "update service",
            )
            service.apply_pending_changes(deployment=new_deployment)

            if service.urls.filter(associated_port__isnull=False).count() > 0:
                ports = (
                    service.urls.filter(associated_port__isnull=False)
                    .values_list("associated_port", flat=True)
                    .distinct()
                )
                for port in ports:
                    DeploymentURL.generate_for_deployment(
                        deployment=new_deployment,
                        service=service,
                        port=port,
                    )

            latest_deployment = service.latest_production_deployment
            new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
            new_deployment.service_snapshot = ServiceSerializer(service).data  # type: ignore
            new_deployment.save()

            payload = DeploymentDetails.from_deployment(deployment=new_deployment)

            transaction.on_commit(
                lambda: start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                )
            )

            response = ServiceDeploymentSerializer(new_deployment)
            return Response(response.data)
