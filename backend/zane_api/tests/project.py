# type: ignore
from unittest.mock import patch

from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..models import (
    Project,
    ArchivedProject,
    DockerRegistryService,
    ArchivedDockerService,
    DockerDeployment,
    Volume,
    DockerEnvVariable,
    PortConfiguration,
    URL,
    DockerDeploymentChange,
    Config,
    ArchivedEnvironment,
    HealthCheck,
    Environment,
)
from ..views import EMPTY_PAGINATED_RESPONSE


class ProjectListViewTests(AuthAPITestCase):
    def test_default(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="thullo"),
            ]
        )

        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("results", [])
        self.assertEqual(1, len(project_list))

    def test_pagination(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
                Project(owner=owner, slug="zaneops"),
            ]
        )

        response = self.client.get(
            reverse("zane_api:projects.list"), QUERY_STRING="per_page=2&page=2"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("results", [])
        self.assertEqual(1, len(project_list))

    def test_pagination_out_of_bands_returns_empty_page(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
                Project(owner=owner, slug="zaneops"),
            ]
        )

        response = self.client.get(
            reverse("zane_api:projects.list"),
            QUERY_STRING="per_page=2&page=3",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(
            EMPTY_PAGINATED_RESPONSE,
            response.json(),
        )

    def test_list_archived(self):
        owner = self.loginUser()

        ArchivedProject.objects.bulk_create(
            [
                ArchivedProject(owner=owner, slug="gh-clone"),
                ArchivedProject(owner=owner, slug="gh-clone2"),
            ]
        )
        response = self.client.get(reverse("zane_api:projects.archived.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("results", [])
        self.assertEqual(2, len(project_list))

    def test_list_filter_slug(self):
        owner = self.loginUser()

        Project.objects.bulk_create(
            [
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
                Project(owner=owner, slug="zaneops"),
            ]
        )
        response = self.client.get(
            reverse("zane_api:projects.list"), QUERY_STRING="slug=gh"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json().get("results", [])
        self.assertEqual(2, len(project_list))

    def test_unauthed(self):
        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_401_UNAUTHORIZED, response.status_code)


class ProjectCreateViewTests(AuthAPITestCase):
    def test_sucessfully_create_project(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())

    def test_create_project_with_description(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={
                "slug": "zane-ops",
                "description": "self-hosted PaaS built on docker swarm",
            },
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())

        created_project: Project = Project.objects.filter().first()
        self.assertEqual(
            "self-hosted PaaS built on docker swarm", created_project.description
        )

    def test_generate_slug_if_not_specified(self):
        self.loginUser()
        response = self.client.post(reverse("zane_api:projects.list"), data={})
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())
        self.assertIsNotNone(Project.objects.filter().first().slug)

    def test_unique_slug(self):
        owner = self.loginUser()
        Project.objects.create(slug="zane-ops", owner=owner)
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)
        self.assertEqual(1, Project.objects.count())

    def test_invalid_slug(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane Ops"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_slug_is_always_lowercase(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-Ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual("zane-ops", Project.objects.filter().first().slug)


class ProjectUpdateViewTests(AuthAPITestCase):
    def test_sucessfully_update_project_slug(self):
        owner = self.loginUser()
        previous_project = Project.objects.create(slug="gh-next", owner=owner)
        response = self.client.patch(
            reverse(
                "zane_api:projects.details", kwargs={"slug": previous_project.slug}
            ),
            data={
                "slug": "kisshub",
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_project: Project = Project.objects.filter(slug="kisshub").first()
        self.assertIsNotNone(updated_project)
        self.assertEqual("kisshub", updated_project.slug)
        self.assertNotEquals(previous_project.updated_at, updated_project.updated_at)

    def test_sucessfully_update_project_description(self):
        owner = self.loginUser()
        previous_project = Project.objects.create(slug="gh-next", owner=owner)
        response = self.client.patch(
            reverse(
                "zane_api:projects.details", kwargs={"slug": previous_project.slug}
            ),
            data={
                "description": "Clone of Github built-on nextjs app router",
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        updated_project: Project = Project.objects.filter(slug="gh-next").first()
        self.assertIsNotNone(updated_project)
        self.assertEqual(
            "Clone of Github built-on nextjs app router", updated_project.description
        )
        self.assertNotEquals(previous_project.updated_at, updated_project.updated_at)

    def test_prevent_empy_update(self):
        owner = self.loginUser()
        previous_project = Project.objects.create(slug="gh-next", owner=owner)
        response = self.client.patch(
            reverse(
                "zane_api:projects.details", kwargs={"slug": previous_project.slug}
            ),
            data={},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_bad_request(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", owner=owner),
                Project(slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"slug": "Zane Ops"},
        )
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)

    def test_non_existent(self):
        self.loginUser()
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"name": "zenops"},
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_already_existing_slug(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", owner=owner),
                Project(slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"slug": "gh-clone"},
            content_type="application/json",
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_can_rename_to_self(self):
        owner = self.loginUser()
        Project.objects.bulk_create(
            [
                Project(slug="gh-clone", owner=owner),
                Project(slug="zane-ops", owner=owner),
            ]
        )
        response = self.client.patch(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"}),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)


class ProjectGetViewTests(AuthAPITestCase):
    def test_sucessfully_get_project(self):
        owner = self.loginUser()
        Project.objects.create(slug="gh-clone", owner=owner),
        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

    def test_non_existent(self):
        self.loginUser()
        response = self.client.get(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)


class ProjectArchiveViewTests(AuthAPITestCase):
    def test_sucessfully_archive_project(self):
        owner = self.loginUser()
        Project.objects.create(
            slug="gh-clone", owner=owner, description="Github clone"
        ),
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNone(updated_project)

        archived_project: ArchivedProject = ArchivedProject.objects.filter(
            slug="gh-clone"
        ).first()

        self.assertIsNotNone(archived_project)
        self.assertNotEquals("", archived_project.original_id)
        self.assertEqual("Github clone", archived_project.description)

    def test_archive_project_should_include_archived_envs(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "gh-clone"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        archived_project: ArchivedProject = ArchivedProject.objects.filter(
            slug="gh-clone"
        ).first()
        archived_envs = ArchivedEnvironment.objects.filter(
            project=archived_project
        ).all()

        self.assertIsNotNone(archived_project)
        self.assertGreater(len(archived_envs), 0)

        deleted_environment_count = Environment.objects.filter(
            project__slug="gh-clone"
        ).count()
        self.assertEqual(0, deleted_environment_count)

    def test_non_existent(self):
        self.loginUser()
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_cannot_archive_already_archived_project(self):
        owner = self.loginUser()
        ArchivedProject.objects.create(slug="zane-ops", owner=owner)
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "zane-ops"})
        )
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

    def test_can_reuse_archived_version_if_it_exists(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)
        ArchivedProject.create_from_project(p)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        updated_project = Project.objects.filter(slug="gh-clone").first()
        self.assertIsNone(updated_project)

        archived_projects = ArchivedProject.objects.filter(slug="gh-clone")
        self.assertEqual(1, len(archived_projects))
        self.assertIsNone(archived_projects.first().active_version)

    async def test_archive_all_services_when_archiving_a_projects(self):
        project, service = await self.acreate_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "name": "caddy-data",
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.HEALTHCHECK,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "type": "COMMAND",
                        "value": "echo 1",
                        "timeout_seconds": 30,
                        "interval_seconds": 30,
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.CONFIGS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "name": "caddyfile",
                        "mount_path": "/etc/caddy/Caddyfile",
                        "contents": "respond hello",
                        "language": "plaintext",
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "USER_UID",
                        "value": "1000",
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.ENV_VARIABLES,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "key": "USER_GID",
                        "value": "1000",
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "gitea.zane.local",
                        "base_path": "/",
                        "strip_prefix": True,
                        "associated_port": 80,
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={"host": 8080, "forwarded": 80},
                ),
            ],
        )

        first_deployment: DockerDeployment = await service.deployments.afirst()
        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": project.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Service is deleted
        deleted_service = await DockerRegistryService.objects.filter(
            slug=service.slug
        ).afirst()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = await (
            ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("volumes")
            .prefetch_related("env_variables")
            .prefetch_related("ports")
            .prefetch_related("urls")
        ).afirst()
        self.assertIsNotNone(archived_service)

        # Deployments are cleaned up
        self.assertEqual(
            0,
            await DockerDeployment.objects.filter(service__slug=service.slug).acount(),
        )

        # Volumes are cleaned up
        deleted_volume = await Volume.objects.filter(name="gitea").afirst()
        self.assertIsNone(deleted_volume)
        self.assertEqual(1, await archived_service.volumes.acount())

        # Configs are cleaned up
        deleted_config = await Config.objects.filter(name="caddyfile").afirst()
        self.assertIsNone(deleted_config)
        self.assertEqual(1, await archived_service.configs.acount())

        # env variables are cleaned up
        deleted_envs = DockerEnvVariable.objects.filter(service__slug=service.slug)
        self.assertEqual(0, await deleted_envs.acount())
        self.assertEqual(2, await archived_service.env_variables.acount())

        # ports are cleaned up
        deleted_ports = PortConfiguration.objects.filter(
            dockerregistryservice__slug=service.slug
        )
        self.assertEqual(0, await deleted_ports.acount())
        self.assertEqual(1, await archived_service.ports.acount())

        # urls are cleaned up
        deleted_urls = URL.objects.filter(domain="gitea.zane.local", base_path="/")
        self.assertEqual(0, await deleted_urls.acount())
        self.assertEqual(2, await archived_service.urls.acount())

        # healthcheck are cleaned up
        deleted_healthcheck = await HealthCheck.objects.filter().afirst()
        self.assertIsNone(deleted_healthcheck)

        # --- Docker Resources ---
        # service is removed
        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            first_deployment
        )
        self.assertIsNone(deleted_docker_service)

        # volumes are unmounted
        self.assertEqual(0, len(self.fake_docker_client.volume_map))


class DockerRemoveNetworkTest(AuthAPITestCase):
    async def test_network_is_deleted_on_archived_project(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        project = await Project.objects.aget(slug="zane-ops")

        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": project.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        archived_project: ArchivedProject = await ArchivedProject.objects.filter(
            original_id=project.id
        ).afirst()
        self.assertIsNotNone(archived_project)
        self.assertIsNone(self.fake_docker_client.get_project_network(project))
        self.assertEqual(0, len(self.fake_docker_client.get_networks()))


class ProjectStatusViewTests(AuthAPITestCase):
    def test_return_status_in_project(self):
        owner = self.loginUser()
        Project.objects.create(owner=owner, slug="thullo")

        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertTrue("healthy_services" in project_in_response)
        self.assertTrue("total_services" in project_in_response)
        self.assertEqual(0, project_in_response.get("healthy_services"))
        self.assertEqual(0, project_in_response.get("total_services"))

    async def test_with_succesful_deploy(self):
        await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(1, project_in_response.get("healthy_services"))
        self.assertEqual(1, project_in_response.get("total_services"))

    async def test_with_multiple_services(self):
        await self.acreate_and_deploy_redis_docker_service()

        with patch(
            "zane_api.temporal.activities.main_activities.monotonic"
        ) as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            await self.acreate_and_deploy_caddy_docker_service()

        response = await self.async_client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(2, project_in_response.get("total_services"))
        self.assertEqual(1, project_in_response.get("healthy_services"))

    async def test_with_failed_deployment(self):
        with patch(
            "zane_api.temporal.activities.main_activities.monotonic"
        ) as mock_monotonic:
            mock_monotonic.side_effect = [0, 31]
            await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(0, project_in_response.get("healthy_services"))
        self.assertEqual(1, project_in_response.get("total_services"))

    async def test_with_unhealthy_deployment(self):
        project, service = await self.acreate_and_deploy_redis_docker_service()

        # make the deployment unhealthy
        deployment: DockerDeployment = await service.deployments.afirst()
        deployment.status = DockerDeployment.DeploymentStatus.UNHEALTHY
        await deployment.asave()

        response = await self.async_client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(0, project_in_response.get("healthy_services"))
        self.assertEqual(1, project_in_response.get("total_services"))


class ProjectResourcesViewTests(AuthAPITestCase):
    def test_show_resources(self):
        self.create_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field="volumes",
                    type="ADD",
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                )
            ]
        )
        p, _ = self.create_and_deploy_caddy_docker_service()

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": p.slug, "env_slug": "production"},
            )
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertTrue(type(response.json()) is list)
        self.assertEqual(2, len(response.json()))

    def test_filter_resources(self):
        self.create_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field="volumes",
                    type="ADD",
                    new_value={
                        "container_path": "/data",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                )
            ]
        )
        p, _ = self.create_and_deploy_caddy_docker_service()

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": p.slug, "env_slug": "production"},
            ),
            QUERY_STRING="query=redis",
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))

    def test_create_service_without_being_deployed_yet(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zaneops"},
        )
        project = Project.objects.get(slug="zaneops")

        create_service_payload = {"slug": "caddy", "image": "caddy:2.8-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={"project_slug": project.slug, "env_slug": "production"},
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": project.slug, "env_slug": "production"},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(1, len(response.json()))
