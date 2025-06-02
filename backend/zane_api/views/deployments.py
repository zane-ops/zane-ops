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
import django.db.transaction as transaction
from .serializers.services import (
    DockerServiceWebhookDeployRequestSerializer,
    GitServiceWebhookDeployRequestSerializer,
    BulkDeployServiceRequestSerializer,
)

from temporal.workflows import DeployDockerServiceWorkflow, DeployGitServiceWorkflow
from rest_framework.utils.serializer_helpers import ReturnDict

from django.db.models import Q, QuerySet, Case, When, Value, IntegerField
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.generics import ListAPIView, RetrieveAPIView

from .base import (
    ResourceConflict,
    EMPTY_PAGINATED_RESPONSE,
)
from .serializers import (
    DockerServiceDeploymentFilterSet,
    DeploymentListPagination,
)

from ..serializers import (
    ServiceDeploymentSerializer,
    ErrorResponse409Serializer,
)
from temporal.main import (
    start_workflow,
    workflow_signal,
)
from temporal.shared import (
    DeploymentDetails,
    CancelDeploymentSignalInput,
)


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
            validated_data = form.validated_data
            cancel_previous = validated_data.get('cancel_previous_deployments', False)

            if cancel_previous:
                active_statuses = [
                    Deployment.DeploymentStatus.QUEUED,
                    Deployment.DeploymentStatus.PREPARING,
                    Deployment.DeploymentStatus.BUILDING,
                    Deployment.DeploymentStatus.STARTING,
                    Deployment.DeploymentStatus.RESTARTING,
                ]
                deployments_to_cancel = Deployment.objects.filter(
                    service=service,
                    status__in=active_statuses
                )
                for active_deployment in deployments_to_cancel:
                    if active_deployment.started_at is None:
                        active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                        active_deployment.status_reason = "Cancelled due to new deployment request."
                        active_deployment.save()
                    else:
                        # Ensure workflow_id is present
                        if active_deployment.workflow_id:
                            transaction.on_commit(
                                lambda ad=active_deployment: workflow_signal( # use lambda with default arg to capture current ad
                                    workflow=DeployDockerServiceWorkflow.run,
                                    arg=CancelDeploymentSignalInput(deployment_hash=ad.hash),
                                    signal=DeployDockerServiceWorkflow.cancel_deployment,
                                    workflow_id=ad.workflow_id,
                                )
                            )
                        else:
                            # Fallback if workflow_id is somehow missing but deployment started
                            active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                            active_deployment.status_reason = "Cancelled (workflow_id missing, fallback)."
                            active_deployment.save()


            new_image = validated_data.get("new_image")

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

            commit_message = validated_data.get("commit_message")
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
            validated_data = form.validated_data
            cancel_previous = validated_data.get('cancel_previous_deployments', False)

            if cancel_previous:
                active_statuses = [
                    Deployment.DeploymentStatus.QUEUED,
                    Deployment.DeploymentStatus.PREPARING,
                    Deployment.DeploymentStatus.BUILDING,
                    Deployment.DeploymentStatus.STARTING,
                    Deployment.DeploymentStatus.RESTARTING,
                ]
                deployments_to_cancel = Deployment.objects.filter(
                    service=service,
                    status__in=active_statuses
                )
                for active_deployment in deployments_to_cancel:
                    if active_deployment.started_at is None:
                        active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                        active_deployment.status_reason = "Cancelled due to new deployment request."
                        active_deployment.save()
                    else:
                        if active_deployment.workflow_id:
                            transaction.on_commit(
                                lambda ad=active_deployment: workflow_signal( # use lambda with default arg to capture current ad
                                    workflow=DeployGitServiceWorkflow.run, # Correct workflow type
                                    arg=CancelDeploymentSignalInput(deployment_hash=ad.hash),
                                    signal=DeployGitServiceWorkflow.cancel_deployment, # Correct signal
                                    workflow_id=ad.workflow_id,
                                )
                            )
                        else:
                            active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                            active_deployment.status_reason = "Cancelled (workflow_id missing, fallback)."
                            active_deployment.save()

            data = validated_data # Use validated_data
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
        validated_data = form.validated_data # Use validated_data
        cancel_previous = validated_data.get('cancel_previous_deployments', False)

        service_ids_to_deploy = validated_data["service_ids"]

        if cancel_previous:
            active_statuses = [
                Deployment.DeploymentStatus.QUEUED,
                Deployment.DeploymentStatus.PREPARING,
                Deployment.DeploymentStatus.BUILDING,
                Deployment.DeploymentStatus.STARTING,
                Deployment.DeploymentStatus.RESTARTING,
            ]
            deployments_to_cancel = Deployment.objects.filter(
                service_id__in=service_ids_to_deploy, # Filter by service_ids from the request
                status__in=active_statuses
            ).select_related('service') # select_related service for type check

            for active_deployment in deployments_to_cancel:
                if active_deployment.started_at is None:
                    active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                    active_deployment.status_reason = "Cancelled due to new bulk deployment request."
                    active_deployment.save()
                else:
                    if active_deployment.workflow_id:
                        workflow_to_signal = None
                        signal_to_use = None
                        if active_deployment.service.type == Service.ServiceType.DOCKER_REGISTRY:
                            workflow_to_signal = DeployDockerServiceWorkflow.run
                            signal_to_use = DeployDockerServiceWorkflow.cancel_deployment
                        elif active_deployment.service.type == Service.ServiceType.GIT_REPOSITORY:
                            workflow_to_signal = DeployGitServiceWorkflow.run
                            signal_to_use = DeployGitServiceWorkflow.cancel_deployment
                        
                        if workflow_to_signal and signal_to_use:
                            transaction.on_commit(
                                # use lambda with default arg to capture current ad, workflow, and signal
                                lambda ad=active_deployment, wf=workflow_to_signal, sig=signal_to_use: workflow_signal(
                                    workflow=wf,
                                    arg=CancelDeploymentSignalInput(deployment_hash=ad.hash),
                                    signal=sig,
                                    workflow_id=ad.workflow_id,
                                )
                            )
                        else:
                            # Fallback if service type is unknown or somehow no workflow/signal assigned
                            active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                            active_deployment.status_reason = "Cancelled (unknown service type for signal, fallback)."
                            active_deployment.save()
                    else:
                        # Fallback if workflow_id is somehow missing but deployment started
                        active_deployment.status = Deployment.DeploymentStatus.CANCELLED
                        active_deployment.status_reason = "Cancelled (workflow_id missing, fallback)."
                        active_deployment.save()

        services = (
            Service.objects.filter(
                Q(project=project)
                & Q(environment=environment)
                & Q(id__in=service_ids_to_deploy) # Use the extracted list
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


class CancelServiceDeploymentAPIView(APIView):
    @transaction.atomic()
    @extend_schema(
        request=None,
        responses={409: ErrorResponse409Serializer, 200: ServiceSerializer},
        operation_id="cancelServiceDeployment",
        summary="Cancel deployment",
        description="Cancel a deployment in progress.",
    )
    def put(
        self,
        request: Request,
        project_slug: str,
        service_slug: str,
        deployment_hash: str,
        env_slug: str = Environment.PRODUCTION_ENV,
    ):
        try:
            project = Project.objects.get(slug=project_slug.lower(), owner=request.user)

            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = (
                Service.objects.filter(
                    Q(slug=service_slug)
                    & Q(project=project)
                    & Q(environment=environment)
                )
                .select_related("project", "healthcheck")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes"
                )
            ).get()
            deployment = service.deployments.get(hash=deployment_hash)  # type: ignore
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with the slug `{service_slug}`"
                f" does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

        if deployment.finished_at is not None or deployment.status not in [
            Deployment.DeploymentStatus.QUEUED,
            Deployment.DeploymentStatus.PREPARING,
            Deployment.DeploymentStatus.BUILDING,
            Deployment.DeploymentStatus.STARTING,
            Deployment.DeploymentStatus.RESTARTING,
        ]:
            raise ResourceConflict(
                detail="This deployment cannot be cancelled as it has already finished "
                "or is in the process of cancelling."
            )

        if deployment.started_at is None:
            deployment.status = Deployment.DeploymentStatus.CANCELLED
            deployment.status_reason = "Deployment cancelled."
            deployment.save()

        if service.type == Service.ServiceType.DOCKER_REGISTRY:
            transaction.on_commit(
                lambda: workflow_signal(
                    workflow=DeployDockerServiceWorkflow.run,
                    arg=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                    signal=DeployDockerServiceWorkflow.cancel_deployment,  # type: ignore
                    workflow_id=deployment.workflow_id,
                )
            )
        else:
            transaction.on_commit(
                lambda: workflow_signal(
                    workflow=DeployGitServiceWorkflow.run,
                    arg=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                    signal=DeployGitServiceWorkflow.cancel_deployment,  # type: ignore
                    workflow_id=deployment.workflow_id,
                )
            )

        response = ServiceDeploymentSerializer(deployment)
        return Response(response.data, status=status.HTTP_200_OK)


class ServiceDeploymentsAPIView(ListAPIView):
    serializer_class = ServiceDeploymentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = DockerServiceDeploymentFilterSet
    pagination_class = DeploymentListPagination
    queryset = (
        Deployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_queryset`

    @extend_schema(
        summary="List all deployments",
        description="List all deployments for a service, the default order is last created descendant.",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e

    def get_queryset(self) -> QuerySet[Deployment]:  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        env_slug = self.kwargs.get("env_slug") or Environment.PRODUCTION_ENV

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = Service.objects.get(
                slug=service_slug, project=project, environment=environment
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
                detail=f"A service with the slug `{service_slug}` does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )

        return (
            Deployment.objects.filter(service=service)
            .select_related("service", "is_redeploy_of")
            .annotate(
                is_healthy=Case(
                    When(status=Deployment.DeploymentStatus.HEALTHY, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("is_healthy", "-queued_at")
        )


class ServiceDeploymentSingleAPIView(RetrieveAPIView):
    serializer_class = ServiceDeploymentSerializer
    lookup_url_kwarg = "deployment_hash"  # This corresponds to the URL configuration
    queryset = (
        Deployment.objects.all()
    )  # This is to document API endpoints with drf-spectacular, in practive what is used is `get_object`

    def get_object(self):  # type: ignore
        project_slug = self.kwargs["project_slug"]
        service_slug = self.kwargs["service_slug"]
        env_slug = self.kwargs.get("env_slug") or Environment.PRODUCTION_ENV
        deployment_hash = self.kwargs["deployment_hash"]

        try:
            project = Project.objects.get(slug=project_slug, owner=self.request.user)
            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
            service = Service.objects.get(
                slug=service_slug, project=project, environment=environment
            )
            deployment: Deployment | None = (
                Deployment.objects.filter(service=service, hash=deployment_hash)
                .select_related("service", "is_redeploy_of")
                .first()
            )
            if deployment is None:
                raise Deployment.DoesNotExist("")
            return deployment
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
                detail=f"A service with the slug `{service_slug}` does not exist within the environment `{env_slug}` of the project `{project_slug}`"
            )
        except Deployment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A deployment with the hash `{deployment_hash}` does not exist for this service."
            )

    @extend_schema(summary="Get single deployment")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
