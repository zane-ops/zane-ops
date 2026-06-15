from typing import cast

from drf_spectacular.utils import extend_schema

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.generics import (
    ListAPIView,
    CreateAPIView,
    RetrieveDestroyAPIView,
    RetrieveUpdateDestroyAPIView,
)

from rest_framework import status
from temporal.client import TemporalClient
from temporal.shared import (
    ArchivedProjectDetails,
    EnvironmentDetails,
    ComposeStackArchiveDetails,
)

from temporal.workflows import (
    RemoveProjectResourcesWorkflow,
)

from ..models import (
    Workspace,
    WorkspaceMembership,
    WorkspaceRole,
    ArchivedProject,
    Service,
    PortConfiguration,
    Volume,
    URL,
    Config,
    ArchivedDockerService,
    ArchivedGitService,
)

from ..constants import WORKSPACE_SESSION_KEY
from .serializers import (
    SwitchWorkspaceRequestSerializer,
    WorkspaceEditPermissionsRequestSerializer,
    WorkspaceTransferOwnershipResponseSerializer,
    WorkspaceTransferOwnershipRequestSerializer,
    WorkspaceMembershipFilterSet,
    WorkspaceMembershipPagination,
    WorkspaceLeaveResponseSerializer,
)
from rest_framework import exceptions
from ..serializers import (
    WorkspaceMembershipSerializer,
    WorkspaceSerializer,
    WorkspaceMemberSerializer,
)
from ..permissions import (
    IsInstanceOwner,
    HasWorkspace,
    IsWorkspaceOwner,
    IsWorkspaceAdmin,
)

from django.db.models import QuerySet, Q
from .base import ResourceConflict, EMPTY_PAGINATED_RESPONSE
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from ee.licensing.models import License, LicenceFeature


class WorkspaceMemberDetailAPIView(RetrieveDestroyAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceMemberSerializer
    lookup_field = "pk"
    lookup_url_kwarg = "membership_id"

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return (
            WorkspaceMembership.objects.filter(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("user")
            .prefetch_related("accessible_projects")
        )

    def perform_destroy(self, instance: WorkspaceMembership):
        current_membership = WorkspaceMembership.objects.get(
            workspace=self.request.workspace,  # type: ignore
            user=self.request.user,
        )

        if instance.user == self.request.user:
            raise ResourceConflict(
                "You cannot remove yourself from the workspace. Contact the owner to remove you from the workspace."
            )

        # We don't need to check for the case of removing another owner
        # as there are DB checks that enforces that a workspace can only
        # have one owner
        if (
            current_membership.role < WorkspaceRole.OWNER
            and instance.role >= WorkspaceRole.ADMIN
        ):
            raise ResourceConflict(
                "You cannot remove another admin or the owner of the workspace."
            )

        return super().perform_destroy(instance)


class EditWorkspaceMemberPermissionsAPIView(APIView):
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]
    serializer_class = WorkspaceMemberSerializer

    @transaction.atomic()
    @extend_schema(
        request=WorkspaceEditPermissionsRequestSerializer,
        operation_id="editWorkpacePermissions",
        summary="Edit workspace membership permissions",
    )
    def put(self, request: Request, membership_id: int):
        try:
            membership = (
                WorkspaceMembership.objects.filter(
                    workspace=self.request.workspace,  # type: ignore
                    id=membership_id,
                )
                .select_related("user")
                .prefetch_related("accessible_projects")
                .get()
            )
        except WorkspaceMembership.DoesNotExist:
            raise exceptions.NotFound()

        if membership.user == self.request.user:
            raise ResourceConflict(
                "You cannot edit your own permissions in the workspace."
            )

        form = WorkspaceEditPermissionsRequestSerializer(
            data=request.data,
            context=dict(
                workspace=self.request.workspace  # type: ignore
            ),
        )
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        membership.role = data["role"]
        membership.save()

        membership.accessible_projects.clear()
        for project in data["accessible_project_ids"]:
            membership.accessible_projects.add(project)

        serializer = WorkspaceMemberSerializer(membership)
        return Response(serializer.data)


class ListWorkspaceMembersAPIView(ListAPIView):
    serializer_class = WorkspaceMemberSerializer
    filter_backends = [DjangoFilterBackend]
    pagination_class = WorkspaceMembershipPagination
    filterset_class = WorkspaceMembershipFilterSet
    permission_classes = [HasWorkspace, IsWorkspaceAdmin]

    queryset = WorkspaceMembership.objects.all()  # just used for the openAPI docs

    @extend_schema(
        summary="List workspace members",
    )
    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except exceptions.NotFound as e:
            if "Invalid page" in str(e.detail):
                return Response(EMPTY_PAGINATED_RESPONSE)
            raise e

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return (
            WorkspaceMembership.objects.filter(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("user")
            .prefetch_related("accessible_projects")
        )


class WorkspaceMembershipListAPIView(ListAPIView):
    serializer_class = WorkspaceMembershipSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[WorkspaceMembership]:  # type: ignore
        return WorkspaceMembership.objects.filter(
            user=self.request.user
        ).select_related("workspace")


class WorkspaceDetailAPIView(RetrieveUpdateDestroyAPIView):
    permission_classes = [HasWorkspace, IsWorkspaceOwner]
    serializer_class = WorkspaceSerializer
    http_method_names = ["put", "delete", "get"]

    def get_object(self) -> Workspace:  # type: ignore
        return self.request.workspace  # type: ignore

    @transaction.atomic()
    def perform_destroy(self, instance):
        workspace = cast(
            Workspace,
            self.request.workspace,  # type: ignore
        )

        workflow_payloads: list[tuple[ArchivedProjectDetails, str]] = []

        for project in workspace.projects.all():
            archived_version = ArchivedProject.get_or_create_from_project(project)

            docker_service_list = (
                Service.objects.filter(Q(project=project))
                .select_related("project", "healthcheck")
                .prefetch_related(
                    "volumes", "ports", "urls", "env_variables", "deployments"
                )
            )
            id_list = []
            for service in docker_service_list:
                if service.deployments.count() > 0:
                    if service.type == Service.ServiceType.DOCKER_REGISTRY:
                        ArchivedDockerService.create_from_service(
                            service, archived_version
                        )
                    else:
                        ArchivedGitService.create_from_service(
                            service, archived_version
                        )
                    id_list.append(service.id)

            PortConfiguration.objects.filter(Q(service__id__in=id_list)).delete()
            URL.objects.filter(Q(service__id__in=id_list)).delete()
            Volume.objects.filter(Q(service__id__in=id_list)).delete()
            Config.objects.filter(Q(service__id__in=id_list)).delete()
            for service in docker_service_list:
                if service.healthcheck is not None:
                    service.healthcheck.delete()
            # Delete Preview metadata before the services because they hold protected references
            # to the services
            for env in project.environments.filter().select_related("preview_metadata"):
                if env.preview_metadata is not None:
                    env.preview_metadata.delete()
            docker_service_list.delete()

            workflow_payloads.append(
                (
                    ArchivedProjectDetails(
                        id=archived_version.pk,
                        original_id=archived_version.original_id,
                        environments=[
                            EnvironmentDetails(
                                id=env.original_id,
                                name=env.name,
                                project_id=archived_version.original_id,
                            )
                            for env in archived_version.environments.all()
                        ],
                        compose_stacks=[
                            ComposeStackArchiveDetails(stack=stack.snapshot)
                            for stack in project.compose_stacks.filter(
                                user_content__isnull=False
                            )
                            .prefetch_related("env_overrides")
                            .all()
                        ],
                    ),
                    archived_version.workflow_id,
                )
            )

        def commit_callback():
            for payload, workflow_id in workflow_payloads:
                TemporalClient.start_workflow(
                    RemoveProjectResourcesWorkflow.run,
                    payload,
                    id=workflow_id,
                )

        transaction.on_commit(commit_callback)

        return super().perform_destroy(instance)

    def delete(self, request, *args, **kwargs):
        response = super().delete(request, *args, **kwargs)

        workspace = cast(
            Workspace,
            self.request.workspace,  # type: ignore
        )

        last_membership = (
            WorkspaceMembership.objects.filter(
                user=self.request.user,
            )
            .exclude(
                workspace_id=workspace.id,
            )
            .select_related("workspace")
            .first()
        )

        request.session[WORKSPACE_SESSION_KEY] = (
            last_membership.workspace.id if last_membership is not None else None
        )

        return response


class CreateWorkspaceAPIView(CreateAPIView):
    permission_classes = [IsInstanceOwner]
    serializer_class = WorkspaceSerializer

    def perform_create(self, serializer: WorkspaceSerializer):
        installed_license = License.get()

        if installed_license is None:
            raise exceptions.PermissionDenied(
                "Creating more than one workspace requires a license. "
                "Please install a license that includes this feature."
            )

        if not installed_license.is_feature_enabled(LicenceFeature.EXTRA_WORKSPACES):
            raise exceptions.PermissionDenied(
                "Your current license plan doesn't include this feature, "
                "so you can only have one workspace. Please upgrade your license to create more."
            )

        super().perform_create(serializer)

        WorkspaceMembership.objects.create(
            user=self.request.user,
            workspace=serializer.instance,
            role=WorkspaceRole.OWNER,
        )

    @extend_schema(
        operation_id="createWorkspace",
        summary="Create a new workspace",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class SwitchWorkspaceAPIView(APIView):
    @extend_schema(
        request=SwitchWorkspaceRequestSerializer,
        responses={
            204: None,
        },
        operation_id="switchWorkspace",
        summary="Switch workspaces",
    )
    def post(self, request: Request) -> Response:
        form = SwitchWorkspaceRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = cast(dict, form.data)

        workspace_id = data.get("workspace_id")

        workspace = Workspace.objects.filter(
            memberships__user=request.user,
            id=workspace_id,
        ).first()

        if workspace is None:
            raise exceptions.NotFound(detail="Workspace not found")

        request.session[WORKSPACE_SESSION_KEY] = workspace.id

        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceLeaveAPIView(APIView):
    serializer_class = WorkspaceLeaveResponseSerializer

    @extend_schema(
        operation_id="leaveWorkspace",
        summary="Leave workspace",
    )
    def post(self, request: Request):
        membership = WorkspaceMembership.objects.get(
            user=self.request.user,
            workspace=self.request.workspace,  # type: ignore
        )

        if membership.role == WorkspaceRole.OWNER:
            raise ResourceConflict(
                "You cannot leave this workspace, to be able to do so, please transfer ownership to another member."
            )
        membership.delete()

        last_membership = (
            WorkspaceMembership.objects.filter(
                user=self.request.user,
            )
            .exclude(
                workspace=self.request.workspace  # type: ignore
            )
            .select_related("workspace")
            .first()
        )

        request.session[WORKSPACE_SESSION_KEY] = (
            last_membership.workspace.id if last_membership is not None else None
        )

        serializer = WorkspaceLeaveResponseSerializer({"success": True})

        return Response(serializer.data, status=status.HTTP_200_OK)


class WorkspaceTransferOwnershipAPIView(APIView):
    permission_classes = [HasWorkspace, IsWorkspaceOwner]
    serializer_class = WorkspaceTransferOwnershipResponseSerializer

    @transaction.atomic()
    @extend_schema(
        request=WorkspaceTransferOwnershipRequestSerializer,
        operation_id="transferWorkspaceOwnership",
        summary="Transfer workspace ownership",
    )
    def post(self, request: Request):
        form = WorkspaceTransferOwnershipRequestSerializer(data=request.data)
        form.is_valid(raise_exception=True)

        data = cast(dict, form.validated_data)

        try:
            new_owner_membership = WorkspaceMembership.objects.get(
                pk=data["new_owner_id"],
                workspace=self.request.workspace,  # type: ignore
            )
        except WorkspaceMembership.DoesNotExist:
            raise exceptions.NotFound("This user is not a member of this workspace.")

        if new_owner_membership.role < WorkspaceRole.ADMIN:
            raise ResourceConflict(
                "You cannot transfer ownership to a non-admin member. Promote them to admin first."
            )

        if new_owner_membership.user == self.request.user:
            raise ResourceConflict("You are already the owner of this workspace.")

        WorkspaceMembership.objects.filter(
            user=self.request.user,
            workspace=self.request.workspace,  # type: ignore
        ).update(role=WorkspaceRole.ADMIN)

        WorkspaceMembership.objects.filter(
            pk=data["new_owner_id"],
            workspace=self.request.workspace,  # type: ignore
        ).update(role=WorkspaceRole.OWNER)

        serializer = WorkspaceTransferOwnershipResponseSerializer({"success": True})
        return Response(serializer.data)
