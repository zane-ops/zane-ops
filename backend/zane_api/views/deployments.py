from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.request import Request

from ..utils import generate_random_chars
from ..serializers import DockerServiceDeploymentSerializer, DockerServiceSerializer
from ..models import (
    DockerRegistryService,
    Project,
    DockerDeployment,
    DockerDeploymentChange,
    DeploymentURL,
)
from django.db.models import Q
import django.db.transaction as transaction
from .serializers import DockerServiceWebhookDeployRequestSerializer
from django.conf import settings
from ..temporal.shared import DockerDeploymentDetails
from ..temporal.main import start_workflow
from ..temporal.workflows import DeployDockerServiceWorkflow


class RegenerateServiceDeployTokenAPIView(APIView):
    serializer_class = DockerServiceSerializer

    @extend_schema(
        summary="Regenerate service deploy token",
        operation_id="regenerateServiceDeployToken",
    )
    def patch(self, request: Request, project_slug: str, service_slug: str):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )

        service = (
            DockerRegistryService.objects.filter(
                Q(slug=service_slug) & Q(project=project)
            )
            .select_related("project")
            .prefetch_related("volumes", "ports", "urls", "env_variables")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the project `{project_slug}`"
            )

        service.deploy_token = generate_random_chars(20)
        service.save()

        response = DockerServiceSerializer(service)
        return Response(response.data)


class WebhookDeployServiceAPIView(APIView):
    serializer_class = DockerServiceDeploymentSerializer
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
            DockerRegistryService.objects.filter(deploy_token=deploy_token)
            .select_related("project")
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
            new_image = form.data.get("new_image")

            if new_image is not None:
                service.add_change(
                    DockerDeploymentChange(
                        type=DockerDeploymentChange.ChangeType.UPDATE,
                        field=DockerDeploymentChange.ChangeField.SOURCE,
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

            commit_message = form.data.get("commit_message")
            new_deployment = DockerDeployment.objects.create(
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
            new_deployment.slot = DockerDeployment.get_next_deployment_slot(
                latest_deployment
            )
            new_deployment.service_snapshot = DockerServiceSerializer(service).data
            new_deployment.save()

            payload = DockerDeploymentDetails.from_deployment(deployment=new_deployment)

            transaction.on_commit(
                lambda: start_workflow(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                )
            )

            response = DockerServiceDeploymentSerializer(new_deployment)
            return Response(response.data)
