# type: ignore
from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    Service,
    Deployment,
    DeploymentChange,
    SharedEnvVariable,
    EnvVariable,
)
from ..utils import jprint
from asgiref.sync import sync_to_async


class CreateGitServiceViewTests(AuthAPITestCase):
    def test_create_simple_git_service(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
            "branch_name": "main",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertIsNotNone(data)

        created_service: Service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()
        self.assertIsNotNone(created_service)

    def test_create_git_service_bad_request(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "image": "ghcr.io/zane-ops/docs",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_git_service_with_non_existent_repository_fails(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": self.fake_git.NON_EXISTENT_REPOSITORY,
            "branch_name": "main",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_create_git_service_with_non_existent_branch_fails(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
            "branch_name": self.fake_git.NON_EXISTENT_BRANCH,
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_creating_git_service_should_create_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zane-ops/docs",
            "branch_name": "main",
            "dockerfile_path": "./app/prod.Dockerfile",
            "build_context_dir": "./app",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        data = response.json()
        self.assertIsNotNone(data)

        created_service: Service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()
        self.assertIsNotNone(created_service)
        source_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.GIT_SOURCE
        ).first()
        builder_change: DeploymentChange = DeploymentChange.objects.filter(
            service=created_service, field=DeploymentChange.ChangeField.BUILDER
        ).first()
        self.assertIsNotNone(source_change)
        self.assertIsNotNone(builder_change)
        self.assertEqual(
            {
                "branch_name": "main",
                "commit_sha": "HEAD",
                "repository_url": "https://github.com/zane-ops/docs.git",
            },
            source_change.new_value,
        )
        print(f"{builder_change.new_value=}")
        self.assertEqual(
            {
                "builder": "DOCKERFILE",
                "options": {
                    "dockerfile_path": "./app/prod.Dockerfile",
                    "build_context_dir": "./app",
                    "build_stage_target": None,
                },
            },
            builder_change.new_value,
        )


class RequestGitServiceChangesViewTests(AuthAPITestCase):
    def test_request_source_changes_image_is_ignored_for_git_service(self):
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.SOURCE,
            "type": "UPDATE",
            "new_value": {
                "image": "ghcr.io/zane-ops/app",
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug=service.slug,
            field=DeploymentChange.ChangeField.SOURCE,
        ).first()
        self.assertIsNone(change)

    def test_request_git_source_changes(self):
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.GIT_SOURCE,
            "type": "UPDATE",
            "new_value": {
                "repository_url": "https://github.com/zaneops/guestbook",
                "branch_name": "master",
                "commit_sha": "123abc7",
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug=service.slug,
            field=DeploymentChange.ChangeField.GIT_SOURCE,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(
            {
                "repository_url": "https://github.com/zaneops/guestbook.git",
                "branch_name": "master",
                "commit_sha": "123abc7",
            },
            change.new_value,
        )


from unittest.mock import patch # Moved to top
from django.utils import timezone # Moved to top
# Deployment, Service, status, reverse are already imported via .base or directly
from zane_api.temporal.workflows import DeployGitServiceWorkflow # Specific to Git
from zane_api.temporal.shared import CancelDeploymentSignalInput
# Removed pytest

class TestDeployGitServiceCancelPrevious(AuthAPITestCase):
    @patch("zane_api.views.git_services.start_workflow")
    @patch("zane_api.views.git_services.workflow_signal")
    async def test_cancel_previous_true_workflow_started(self, mock_workflow_signal, mock_start_workflow):
        project, service = await self.acreate_git_service_with_env()
        await service.unapplied_changes.all().adelete() # Clear initial changes

        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_wf_id_git_deploy_old",
            started_at=timezone.now(),
            commit_sha="oldcommit" # Git deployments need a commit_sha
        )

        url = reverse(
            "zane_api:services.git.deploy_service",
            kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        # Git deploy serializer expects 'ignore_build_cache'
        payload = {"cancel_previous_deployments": True, "ignore_build_cache": False}
        response = await self.async_client.put(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_workflow_signal.assert_called_once()

        args, called_kwargs = mock_workflow_signal.call_args
        self.assertEqual(called_kwargs["workflow"], DeployGitServiceWorkflow.run)
        self.assertEqual(called_kwargs["signal"], DeployGitServiceWorkflow.cancel_deployment)
        self.assertIsInstance(called_kwargs["arg"], CancelDeploymentSignalInput)
        self.assertEqual(called_kwargs["arg"].deployment_hash, old_deployment.hash)
        self.assertEqual(called_kwargs["workflow_id"], old_deployment.workflow_id)

        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)

    @patch("zane_api.views.git_services.start_workflow")
    async def test_cancel_previous_true_workflow_not_started(self, mock_start_workflow):
        project, service = await self.acreate_git_service_with_env()
        await service.unapplied_changes.all().adelete()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.QUEUED,
            started_at=None,
            commit_sha="oldcommit_notstarted"
        )

        url = reverse(
            "zane_api:services.git.deploy_service",
             kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": True, "ignore_build_cache": False}
        response = await self.async_client.put(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        await old_deployment.arefresh_from_db()
        self.assertEqual(old_deployment.status, Deployment.DeploymentStatus.CANCELLED)
        self.assertIn("Cancelled due to new UI-triggered deployment.", old_deployment.status_reason)
        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)

    @patch("zane_api.views.git_services.start_workflow")
    @patch("zane_api.views.git_services.workflow_signal")
    async def test_cancel_previous_false_workflow_started(self, mock_workflow_signal, mock_start_workflow):
        project, service = await self.acreate_git_service_with_env()
        await service.unapplied_changes.all().adelete()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_wf_id_git_deploy_false",
            started_at=timezone.now(),
            commit_sha="oldcommit_false"
        )

        url = reverse(
            "zane_api:services.git.deploy_service",
            kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": False, "ignore_build_cache": False}
        response = await self.async_client.put(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_workflow_signal.assert_not_called()
        await old_deployment.arefresh_from_db()
        self.assertEqual(old_deployment.status, Deployment.DeploymentStatus.STARTING)
        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)

    @patch("zane_api.views.git_services.start_workflow")
    @patch("zane_api.views.git_services.workflow_signal")
    async def test_cancel_previous_true_no_active_deployments(self, mock_workflow_signal, mock_start_workflow):
        project, service = await self.acreate_git_service_with_env()
        await service.unapplied_changes.all().adelete()
        await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.HEALTHY,
            workflow_id="fake_wf_id_git_deploy_healthy",
            started_at=timezone.now(),
            commit_sha="oldcommit_healthy"
        )

        url = reverse(
            "zane_api:services.git.deploy_service",
            kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": True, "ignore_build_cache": False}
        response = await self.async_client.put(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_workflow_signal.assert_not_called()
        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)
        new_depl = await Deployment.objects.aget(service=service, status=Deployment.DeploymentStatus.QUEUED)
        self.assertIsNotNone(new_depl)
#### End of new tests for DeployGitServiceAPIView ####

    def test_request_git_builder_changes(self):
        p, service = self.create_git_service()

        changes_payload = {
            "field": DeploymentChange.ChangeField.BUILDER,
            "type": "UPDATE",
            "new_value": {
                "builder": "DOCKERFILE",
                "build_context_dir": "./app",
                "dockerfile_path": "./app.Dockerfile",
                "build_stage_target": "builder",
            },
        }

        response = self.client.put(
            reverse(
                "zane_api:services.request_deployment_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
            data=changes_payload,
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        change: DeploymentChange = DeploymentChange.objects.filter(
            service__slug=service.slug,
            field=DeploymentChange.ChangeField.BUILDER,
        ).first()
        self.assertIsNotNone(change)
        self.assertEqual(
            {
                "builder": "DOCKERFILE",
                "options": {
                    "build_context_dir": "./app",
                    "dockerfile_path": "./app.Dockerfile",
                    "build_stage_target": "builder",
                },
            },
            change.new_value,
        )


class CancelGitServiceChangesViewTests(AuthAPITestCase):
    def test_can_cancel_simple_changes(self):
        p, service = self.create_git_service()

        change = DeploymentChange.objects.create(
            field=DeploymentChange.ChangeField.COMMAND,
            type=DeploymentChange.ChangeType.UPDATE,
            new_value="echo 1",
            service=service,
        )

        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        change_count = DeploymentChange.objects.filter(
            service=service, applied=False
        ).count()
        self.assertEqual(2, change_count)

    def test_cannot_cancel_git_source_change_if_it_sets_repository_to_null(self):
        p, service = self.create_git_service()

        change = service.unapplied_changes.filter(
            field=DeploymentChange.ChangeField.GIT_SOURCE
        ).first()

        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_cancel_git_source_change_if_it_sets_builder_to_null(self):
        p, service = self.create_git_service()

        change = service.unapplied_changes.filter(
            field=DeploymentChange.ChangeField.BUILDER
        ).first()

        response = self.client.delete(
            reverse(
                "zane_api:services.cancel_service_changes",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "change_id": change.id,
                },
            ),
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)


class DeployGitServiceViewTests(AuthAPITestCase):
    def test_deploy_git_service_apply_pending_changes(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = Project.objects.get(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
            "branch_name": "main",
        }
        response = self.client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service: Service = Service.objects.filter(
            slug="docs", type=Service.ServiceType.GIT_REPOSITORY
        ).first()

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        service.refresh_from_db()
        self.assertEqual("https://github.com/zaneops/docs.git", service.repository_url)
        self.assertEqual("main", service.branch_name)
        self.assertEqual(Service.Builder.DOCKERFILE, service.builder)
        self.assertEqual(
            {
                "dockerfile_path": "./Dockerfile",
                "build_context_dir": "./",
                "build_stage_target": None,
            },
            service.dockerfile_builder_options,
        )

    def test_deploy_simple_service_create_deployment_with_commit_sha(self):
        p, service = self.create_git_service()

        response = self.client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertEqual(1, service.deployments.count())

        latest_deployment: Deployment = service.deployments.first()
        self.assertIsNotNone(latest_deployment.commit_sha)
        self.assertNotEqual("HEAD", latest_deployment.commit_sha)

    async def test_deploy_git_service_build_and_deploy_service(self):
        p, service = await self.acreate_and_deploy_git_service()
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)

    async def test_deploy_git_service_include_all_envs_as_buildargs(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        p = await Project.objects.aget(slug="zane-ops")

        create_service_payload = {
            "slug": "docs",
            "repository_url": "https://github.com/zaneops/docs",
            "branch_name": "main",
        }
        response = await self.async_client.post(
            reverse(
                "zane_api:services.git.create",
                kwargs={"project_slug": p.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service: Service = await (
            Service.objects.filter(slug="docs")
            .select_related("environment")
            .prefetch_related("env_variables")
            .afirst()
        )

        await SharedEnvVariable.objects.abulk_create(
            [
                SharedEnvVariable(
                    key="GITHUB_CLIENT_ID",
                    value="superSecret",
                    environment=service.environment,
                ),
                SharedEnvVariable(
                    key="GITHUB_TOKEN",
                    value="superSecret",
                    environment=service.environment,
                ),
            ]
        )

        await EnvVariable.objects.abulk_create(
            [
                EnvVariable(
                    key="SESSION_DOMAIN", value="hello.fredkiss.dev", service=service
                ),
                EnvVariable(key="SESSION_SECURE", value="true", service=service),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNotNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.HEALTHY, new_deployment.status)
        self.assertTrue(new_deployment.is_current_production)

        fake_image = None
        for image in self.fake_docker_client.image_map.values():
            if new_deployment.image_tag in image.tags:
                fake_image = image
                break
        self.assertIsNotNone(fake_image)
        jprint(fake_image.buildargs)

        # Include all service env variables
        self.assertTrue(
            all(
                [
                    env.key in fake_image.buildargs
                    async for env in service.env_variables.all()
                ]
            )
        )
        # Include all environment variables
        self.assertTrue(
            all(
                [
                    env.key in fake_image.buildargs
                    async for env in service.environment.variables.all()
                ]
            )
        )
        # Include all system variables
        self.assertTrue(
            all(
                [
                    env["key"] in fake_image.buildargs
                    for env in await sync_to_async(
                        lambda: service.system_env_variables
                    )()
                ]
            )
        )

    async def test_deploy_git_service_error_when_building_dockerfile_fails_the_build(
        self,
    ):
        p, service = await self.acreate_and_deploy_git_service(
            dockerfile=f"./{self.fake_docker_client.BAD_DOCKERFILE}"
        )
        new_deployment: Deployment = await service.alatest_production_deployment
        self.assertIsNotNone(new_deployment)
        swarm_service = self.fake_docker_client.get_deployment_service(new_deployment)
        self.assertIsNone(swarm_service)
        self.assertEqual(Deployment.DeploymentStatus.FAILED, new_deployment.status)


class ProjectServiceListWithGitServicesViewTests(AuthAPITestCase):
    def test_show_git_resources(self):
        self.create_git_service()
        p, _ = self.create_redis_docker_service()

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": p.slug, "env_slug": "production"},
            )
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(type(response.json()) is list)
        self.assertEqual(2, len(response.json()))


class RedeployGitServiceViewTests(AuthAPITestCase):
    async def test_redeploy_git_service_create_deployment_with_computed_changes(self):
        project, service = await self.acreate_and_deploy_git_service(
            repository="https://github.com/zaneops/docs"
        )
        initial_deployment: Deployment = await service.deployments.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.GIT_SOURCE,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "repository_url": "https://github.com/zaneops/guestbook.git",
                        "branch_name": "feat/update-react-router",
                        "commit_sha": "abcd123",
                    },
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        # Redeploy
        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())

        last_deployment: Deployment = await (
            service.deployments.order_by("-queued_at")
            .select_related("is_redeploy_of")
            .afirst()
        )
        self.assertIsNotNone(last_deployment.service_snapshot)
        self.assertEqual(initial_deployment, last_deployment.is_redeploy_of)
        self.assertEqual(1, await last_deployment.changes.acount())

        change: DeploymentChange = await last_deployment.changes.filter(
            field=DeploymentChange.ChangeField.GIT_SOURCE
        ).afirst()
        self.assertIsNotNone(change)
        self.assertEqual(DeploymentChange.ChangeType.UPDATE, change.type)

        self.assertEqual(
            "https://github.com/zaneops/guestbook.git",
            change.old_value.get("repository_url"),
        )
        self.assertEqual(
            "https://github.com/zaneops/docs.git",
            change.new_value.get("repository_url"),
        )
        self.assertEqual("main", change.new_value.get("branch_name"))
        self.assertEqual(
            "feat/update-react-router", change.old_value.get("branch_name")
        )
        self.assertEqual(
            initial_deployment.commit_sha, change.new_value.get("commit_sha")
        )
        self.assertEqual("abcd123", change.old_value.get("commit_sha"))

        await service.arefresh_from_db()
        self.assertEqual("https://github.com/zaneops/docs.git", service.repository_url)
        self.assertEqual("main", service.branch_name)
        self.assertEqual(initial_deployment.commit_sha, service.commit_sha)

    async def test_redeploy_git_service_reapply_old_builder_changes(self):
        project, service = await self.acreate_and_deploy_git_service()

        initial_deployment: Deployment = await service.deployments.afirst()

        await DeploymentChange.objects.abulk_create(
            [
                DeploymentChange(
                    field=DeploymentChange.ChangeField.BUILDER,
                    type=DeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "builder": Service.Builder.DOCKERFILE,
                        "options": {
                            "dockerfile_path": "./app/rails/Dockerfile",
                            "build_context_dir": "./",
                            "build_stage_target": "builder",
                        },
                    },
                    service=service,
                ),
            ]
        )
        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.deploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        # Redeploy
        response = await self.async_client.put(
            reverse(
                "zane_api:services.git.redeploy_service",
                kwargs={
                    "project_slug": project.slug,
                    "env_slug": "production",
                    "service_slug": service.slug,
                    "deployment_hash": initial_deployment.hash,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(3, await service.deployments.acount())
        last_deployment: Deployment = await (
            service.deployments.order_by("-queued_at")
            .select_related("is_redeploy_of")
            .afirst()
        )
        self.assertIsNotNone(last_deployment.service_snapshot)
        self.assertEqual(initial_deployment, last_deployment.is_redeploy_of)
        self.assertEqual(1, await last_deployment.changes.acount())

        change: DeploymentChange = await last_deployment.changes.filter(
            field=DeploymentChange.ChangeField.BUILDER
        ).afirst()
        self.assertIsNotNone(change)
        self.assertEqual(DeploymentChange.ChangeType.UPDATE, change.type)

        self.assertEqual(
            {
                "builder": Service.Builder.DOCKERFILE,
                "options": {
                    "dockerfile_path": "./app/rails/Dockerfile",
                    "build_context_dir": "./",
                    "build_stage_target": "builder",
                },
            },
            change.old_value,
        )
        self.assertEqual(
            {
                "builder": Service.Builder.DOCKERFILE,
                "options": {
                    "dockerfile_path": "./Dockerfile",
                    "build_context_dir": "./",
                    "build_stage_target": None,
                },
            },
            change.new_value,
        )
