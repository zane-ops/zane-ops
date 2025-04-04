from typing import Any, Callable, List, Tuple, cast
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework import status

from ..git_client import GitClient

from ..utils import generate_random_chars
from ..serializers import ServiceSerializer
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
from .serializers import (
    DockerServiceWebhookDeployRequestSerializer,
    GitServiceWebhookDeployRequestSerializer,
    BulkDeployServiceRequestSerializer,
)
from ..temporal.shared import DeploymentDetails
from ..temporal.main import start_workflow
from ..temporal.workflows import DeployDockerServiceWorkflow, DeployGitServiceWorkflow
from rest_framework.utils.serializer_helpers import ReturnDict


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


class WebhookDeployDockerServiceAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "deploy_webhook"

    @transaction.atomic()
    @extend_schema(
        request=DockerServiceWebhookDeployRequestSerializer,
        responses={202: None},
        operation_id="webhookDockerDeployService",
        summary="Webhook to deploy a docker service",
        description="trigger a new deployment.",
    )
    def put(self, request: Request, deploy_token: str):

        service = (
            Service.objects.filter(
                deploy_token=deploy_token, type=Service.ServiceType.DOCKER_REGISTRY
            )
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
                source_change = service.unapplied_changes.filter(
                    field=DeploymentChange.ChangeField.SOURCE
                ).first()

                if source_change is not None:
                    source_change.new_value["image"] = new_image  # type: ignore - override the image change
                    source_change.save()
                else:
                    # `source_change` will be None if the case of an already deployed service
                    # so the image and credentials are valid
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
                trigger_method=Deployment.DeploymentTriggerMethod.WEBHOOK,
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

            return Response(status=status.HTTP_202_ACCEPTED)


class WebhookDeployGitServiceAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "deploy_webhook"

    @transaction.atomic()
    @extend_schema(
        request=DockerServiceWebhookDeployRequestSerializer,
        responses={202: None},
        operation_id="webhookGitDeployService",
        summary="Webhook to deploy a git service",
        description="trigger a new deployment.",
    )
    def put(self, request: Request, deploy_token: str):

        service = (
            Service.objects.filter(
                deploy_token=deploy_token, type=Service.ServiceType.GIT_REPOSITORY
            )
            .select_related("project", "healthcheck", "environment")
            .prefetch_related("volumes", "ports", "urls", "env_variables", "changes")
        ).first()

        if service is None:
            raise exceptions.NotFound(
                detail=f"A service with a deploy_token `{deploy_token}` doesn't exist."
            )

        form = GitServiceWebhookDeployRequestSerializer(
            data=request.data or {},
        )
        if form.is_valid(raise_exception=True):
            data = cast(ReturnDict, form.data)
            new_commit_sha = data["commit_sha"]

            source_change = service.unapplied_changes.filter(
                field=DeploymentChange.ChangeField.GIT_SOURCE
            ).first()

            if new_commit_sha != service.commit_sha:
                if source_change is None:
                    service.add_change(
                        DeploymentChange(
                            type=DeploymentChange.ChangeType.UPDATE,
                            field=DeploymentChange.ChangeField.GIT_SOURCE,
                            old_value={
                                "repository_url": service.repository_url,
                                "branch_name": service.branch_name,
                                "commit_sha": service.commit_sha,
                            },
                            new_value={
                                "repository_url": service.repository_url,
                                "branch_name": service.branch_name,
                                "commit_sha": new_commit_sha,
                            },
                            service=service,
                        )
                    )
                else:
                    source_change.new_value["commit_sha"] = new_commit_sha  # type: ignore - overwrite the commit sha
                    source_change.save()

            new_deployment = Deployment.objects.create(
                service=service,
                commit_message="-",
                ignore_build_cache=data["ignore_build_cache"],
                trigger_method=Deployment.DeploymentTriggerMethod.WEBHOOK,
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

            commit_sha = service.commit_sha
            if commit_sha == "HEAD":
                git_client = GitClient()
                commit_sha = git_client.resolve_commit_sha_for_branch(service.repository_url, service.branch_name) or "HEAD"  # type: ignore

            new_deployment.commit_sha = commit_sha

            latest_deployment = service.latest_production_deployment
            new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
            new_deployment.service_snapshot = ServiceSerializer(service).data  # type: ignore
            new_deployment.save()

            payload = DeploymentDetails.from_deployment(deployment=new_deployment)

            transaction.on_commit(
                lambda: start_workflow(
                    workflow=DeployGitServiceWorkflow.run,
                    arg=payload,
                    id=payload.workflow_id,
                )
            )

            return Response(status=status.HTTP_202_ACCEPTED)


class BulkDeployServicesAPIView(APIView):

    @extend_schema(
        request=BulkDeployServiceRequestSerializer,
        responses={202: None},
        operation_id="bulkDeployServices",
        summary="Bulk deploy services",
        description="Deploy all selected services in an environment",
    )
    @transaction.atomic()
    def put(self, request: Request, project_slug: str, env_slug: str) -> Response:
        try:
            project = Project.objects.get(slug=project_slug.lower())
            environment = project.environments.get(name=env_slug.lower())
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A env with the slug `{env_slug}` does not exist in this project"
            )

        form = BulkDeployServiceRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        services = (
            Service.objects.filter(
                Q(project=project)
                & Q(environment=environment)
                & Q(id__in=data["service_ids"])
            )
            .select_related("healthcheck", "project", "environment")
            .prefetch_related(
                "volumes", "ports", "urls", "env_variables", "changes", "configs"
            )
        )

        workflows_to_run: List[Tuple[Callable, Any, str]] = []

        for service in services:
            if service.type == Service.ServiceType.DOCKER_REGISTRY:
                new_deployment = Deployment.objects.create(
                    service=service,
                    commit_message="bulk deploy via UI",
                    trigger_method=Deployment.DeploymentTriggerMethod.MANUAL,
                )
            else:
                new_deployment = Deployment.objects.create(
                    service=service,
                    commit_message="-",
                    trigger_method=Deployment.DeploymentTriggerMethod.MANUAL,
                )
            service.apply_pending_changes(new_deployment)

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

            if service.type == Service.ServiceType.GIT_REPOSITORY:
                commit_sha = service.commit_sha
                if commit_sha == "HEAD":
                    git_client = GitClient()
                    commit_sha = git_client.resolve_commit_sha_for_branch(service.repository_url, service.branch_name) or "HEAD"  # type: ignore

                new_deployment.commit_sha = commit_sha

            latest_deployment = service.latest_production_deployment
            new_deployment.slot = Deployment.get_next_deployment_slot(latest_deployment)
            new_deployment.service_snapshot = ServiceSerializer(service).data  # type: ignore
            new_deployment.save()
            payload = DeploymentDetails.from_deployment(deployment=new_deployment)

            workflows_to_run.append(
                (
                    (
                        DeployDockerServiceWorkflow.run
                        if service.type == Service.ServiceType.DOCKER_REGISTRY
                        else DeployGitServiceWorkflow.run
                    ),
                    payload,
                    payload.workflow_id,
                )
            )

        transaction.on_commit(
            lambda: [
                start_workflow(
                    workflow,
                    payload,
                    workflow_id,
                )
                for workflow, payload, workflow_id in workflows_to_run
            ]
        )

        return Response(status=status.HTTP_202_ACCEPTED)
