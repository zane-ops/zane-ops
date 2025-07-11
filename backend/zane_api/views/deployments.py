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
from .serializers import (
    DockerServiceWebhookDeployRequestSerializer,
    GitServiceWebhookDeployRequestSerializer,
    BulkDeployServiceRequestSerializer,
    DeploymentCleanupQueueSerializer,
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
# from temporal.client import TemporalClient # No longer used directly for starting deployments
from temporal.shared import (
    # DeploymentDetails, # Handled by DeploymentService
    CancelDeploymentSignalInput, # Still used for signaling other workflows
)
from ..services.deployment_service import DeploymentService, DeploymentSetupError # Import new service
from temporal.workflows import DeployDockerServiceWorkflow, DeployGitServiceWorkflow # Still needed for signaling


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

        try:
            service = (
                Service.objects.filter(
                    deploy_token=deploy_token,
                    type=Service.ServiceType.DOCKER_REGISTRY,
                )
                .select_related("project", "healthcheck", "environment")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes"
                )
            ).get()
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with a deploy_token `{deploy_token}` doesn't exist."
            )

        form = DockerServiceWebhookDeployRequestSerializer(
            data=request.data if request.data is not None else {},
            context={"service": service},
        )
        if form.is_valid(raise_exception=True):
            data = cast(ReturnDict, form.data)

            deployments_to_cancel = []
            if data.get("cleanup_queue"):
                deployments_to_cancel = Deployment.flag_deployments_for_cancellation(
                    service, include_running_deployments=True
                )

            new_image = data.get("new_image")

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

            commit_message = data.get("commit_message")
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
            deployment_service = DeploymentService()
            try:
                new_deployment, deployments_to_cancel_instances = deployment_service.setup_docker_deployment(
                    service=service,
                    request_data=data, # form.data
                    trigger_method=Deployment.DeploymentTriggerMethod.WEBHOOK,
                    webhook_new_image=new_image
                )
            except DeploymentSetupError as e:
                raise exceptions.APIException(str(e), code=status.HTTP_400_BAD_REQUEST)

            def commit_callback():
                import asyncio
                async def trigger():
                    await deployment_service.trigger_deployment_workflow(
                        deployment_id=new_deployment.id,
                        deployments_to_cancel_ids=[d.id for d in deployments_to_cancel_instances]
                    )
                try:
                    asyncio.run(trigger())
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(trigger())
                    else:
                        loop.run_until_complete(trigger())

            transaction.on_commit(commit_callback)

            return Response(status=status.HTTP_202_ACCEPTED)


class WebhookDeployGitServiceAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "deploy_webhook"

    @transaction.atomic()
    @extend_schema(
        request=GitServiceWebhookDeployRequestSerializer,
        responses={202: None},
        operation_id="webhookGitDeployService",
        summary="Webhook to deploy a git service",
        description="trigger a new deployment.",
    )
    def put(self, request: Request, deploy_token: str):
        try:
            service = (
                Service.objects.filter(
                    deploy_token=deploy_token,
                    type=Service.ServiceType.GIT_REPOSITORY,
                )
                .select_related("project", "healthcheck", "environment")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "changes"
                )
            ).get()
        except Service.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"A service with a deploy_token `{deploy_token}` doesn't exist."
            )

        form = GitServiceWebhookDeployRequestSerializer(
            data=request.data or {},
        )
        if form.is_valid(raise_exception=True):
            data = cast(ReturnDict, form.data)

            deployments_to_cancel = []
            if data.get("cleanup_queue"):
                deployments_to_cancel = Deployment.flag_deployments_for_cancellation(
                    service, include_running_deployments=True
                )

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
            deployment_service = DeploymentService()
            try:
                new_deployment, deployments_to_cancel_instances = deployment_service.setup_git_deployment(
                    service=service,
                    request_data=data, # form.data
                    trigger_method=Deployment.DeploymentTriggerMethod.WEBHOOK,
                    webhook_new_commit_sha=new_commit_sha
                )
            except DeploymentSetupError as e:
                raise exceptions.APIException(str(e), code=status.HTTP_400_BAD_REQUEST)

            def commit_callback():
                import asyncio
                async def trigger():
                    await deployment_service.trigger_deployment_workflow(
                        deployment_id=new_deployment.id,
                        deployments_to_cancel_ids=[d.id for d in deployments_to_cancel_instances]
                    )
                try:
                    asyncio.run(trigger())
                except RuntimeError:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(trigger())
                    else:
                        loop.run_until_complete(trigger())

            transaction.on_commit(commit_callback)

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
            # For bulk, we need to collect all deployment IDs and their types
            # The DeploymentService's setup methods will create and save each deployment.
            # The trigger method in DeploymentService will then handle starting the workflows.

            deployment_service = DeploymentService()
            # This list will now store tuples of (deployment_id, service_type, ignore_build_cache_if_git)
            # to be passed to a bulk trigger method in DeploymentService.
            # Note: The current `trigger_deployment_workflow` is singular.
            # We might need a `trigger_bulk_deployment_workflows` or call the singular one in a loop.
            # For now, let's adapt to call the singular one in a loop in the commit_callback.

            # Store details needed for triggering post-commit
            created_deployments_info: List[Tuple[str, Service.ServiceType, bool]] = []


            # This part of the loop needs to be outside transaction.atomic() if setup_... methods are async.
            # However, they are currently synchronous.
            # The main issue is that `service.apply_pending_changes` and `new_deployment.save()`
            # should be part of the atomic transaction.

            for service_instance in services: # Renamed from `service` to `service_instance` to avoid conflict
                request_data_for_service = data # BulkDeployServiceRequestSerializer doesn't have per-service data currently
                                                # It only has service_ids. We assume default options for each.
                                                # If ignore_build_cache or commit_message were per-service, this would need adjustment.

                # Create a dictionary that can be passed as request_data to setup methods
                # For bulk, there's no specific per-service data in the request other than service_ids
                # So, we pass an empty dict for 'request_data' or specific defaults if needed.
                # The `BulkDeployServiceRequestSerializer` only has `service_ids`.
                # We need to ensure `setup_..._deployment` can handle minimal `request_data`.
                # It primarily uses it for `commit_message` and `ignore_build_cache`.
                # For bulk, let's use generic messages.
                current_service_request_data = {}
                if service_instance.type == Service.ServiceType.GIT_REPOSITORY:
                    current_service_request_data["ignore_build_cache"] = False # Default for bulk

                try:
                    if service_instance.type == Service.ServiceType.DOCKER_REGISTRY:
                        new_deployment, _ = deployment_service.setup_docker_deployment(
                            service=service_instance,
                            request_data=current_service_request_data, # Empty or default data
                            trigger_method=Deployment.DeploymentTriggerMethod.MANUAL
                        )
                    else: # GIT_REPOSITORY
                        new_deployment, _ = deployment_service.setup_git_deployment(
                            service=service_instance,
                            request_data=current_service_request_data, # Empty or default data
                            trigger_method=Deployment.DeploymentTriggerMethod.MANUAL
                        )
                    created_deployments_info.append(
                        (new_deployment.id, service_instance.type, new_deployment.ignore_build_cache)
                    )
                except DeploymentSetupError as e:
                    # In a bulk operation, we might choose to log this and continue,
                    # or fail the entire bulk operation. For now, let's raise,
                    # which will roll back the transaction.
                    raise exceptions.APIException(
                        f"Error setting up deployment for service {service_instance.slug}: {str(e)}",
                        code=status.HTTP_400_BAD_REQUEST
                    )


        def commit_callback():
            import asyncio
            async def trigger_all():
                # Use the new bulk trigger method
                await deployment_service.trigger_bulk_deployment_workflows(created_deployments_info)

            try:
                asyncio.run(trigger_all())
            except RuntimeError:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(trigger_all())
                else:
                    loop.run_until_complete(trigger_all())

        transaction.on_commit(commit_callback)

        return Response(status=status.HTTP_202_ACCEPTED)


class CleanupDeploymentQueueAPIView(APIView):

    @extend_schema(
        request=DeploymentCleanupQueueSerializer,
        responses={202: None},
        operation_id="cleanupDeploymentQueue",
        summary="Cleanup Deployment queue",
        description="Cleanup the current running deployment queue",
    )
    @transaction.atomic()
    def put(
        self,
        request: Request,
        project_slug: str,
        env_slug: str,
        service_slug: str,
    ) -> Response:
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

        form = DeploymentCleanupQueueSerializer(data=request.data or {})
        form.is_valid(raise_exception=True)
        data = cast(ReturnDict, form.data)

        deployments_to_cancel = Deployment.flag_deployments_for_cancellation(
            service=service,
            include_running_deployments=data["cancel_running_deployments"],
        )

        def commit_callback():
            for dpl in deployments_to_cancel:
                TemporalClient.workflow_signal(
                    workflow=(
                        DeployDockerServiceWorkflow.run
                        if service.type == Service.ServiceType.DOCKER_REGISTRY
                        else DeployGitServiceWorkflow.run
                    ),  # type: ignore
                    input=CancelDeploymentSignalInput(deployment_hash=dpl.hash),
                    signal=(
                        DeployDockerServiceWorkflow.cancel_deployment
                        if service.type == Service.ServiceType.DOCKER_REGISTRY
                        else DeployGitServiceWorkflow.cancel_deployment
                    ),  # type: ignore
                    workflow_id=dpl.workflow_id,
                )

        transaction.on_commit(commit_callback)

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
                lambda: TemporalClient.workflow_signal(
                    workflow=DeployDockerServiceWorkflow.run,
                    input=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
                    signal=DeployDockerServiceWorkflow.cancel_deployment,  # type: ignore
                    workflow_id=deployment.workflow_id,
                )
            )
        else:
            transaction.on_commit(
                lambda: TemporalClient.workflow_signal(
                    workflow=DeployGitServiceWorkflow.run,
                    input=CancelDeploymentSignalInput(deployment_hash=deployment.hash),
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
