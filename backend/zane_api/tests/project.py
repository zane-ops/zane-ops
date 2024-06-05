from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..docker_operations import (
    get_swarm_service_name_for_deployment,
)
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

    def test_archive_all_services_when_archiving_a_projects(self):
        project, service = self.create_and_deploy_caddy_docker_service(
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
                    },
                ),
            ]
        )

        first_deployment: DockerDeployment = service.deployments.first()
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": project.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Service is deleted
        deleted_service = DockerRegistryService.objects.filter(
            slug=service.slug
        ).first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(original_id=service.id)
            .prefetch_related("volumes")
            .prefetch_related("env_variables")
            .prefetch_related("ports")
            .prefetch_related("urls")
        ).first()
        self.assertIsNotNone(archived_service)

        # Deployments are cleaned up
        deployments = DockerDeployment.objects.filter(service__slug=service.slug)
        self.assertEqual(0, deployments.count())

        # Volumes are cleaned up
        deleted_volume = Volume.objects.filter(name="gitea").first()
        self.assertIsNone(deleted_volume)
        self.assertEqual(1, archived_service.volumes.count())

        # env variables are cleaned up
        deleted_envs = DockerEnvVariable.objects.filter(service__slug=service.slug)
        self.assertEqual(0, deleted_envs.count())
        self.assertEqual(2, archived_service.env_variables.count())

        # ports are cleaned up
        deleted_ports = PortConfiguration.objects.filter(
            dockerregistryservice__slug=service.slug
        )
        self.assertEqual(0, deleted_ports.count())
        self.assertEqual(1, archived_service.ports.count())

        # urls are cleaned up
        deleted_urls = URL.objects.filter(domain="gitea.zane.local", base_path="/")
        self.assertEqual(0, deleted_urls.count())
        self.assertEqual(1, archived_service.urls.count())

        # --- Docker Resources ---
        # service is removed
        service_name = get_swarm_service_name_for_deployment(
            (
                archived_service.project.original_id,
                archived_service.original_id,
                first_deployment.hash,
            )
        )
        deleted_docker_service = self.fake_docker_client.service_map.get(service_name)
        self.assertIsNone(deleted_docker_service)

        # volumes are unmounted
        self.assertEqual(0, len(self.fake_docker_client.volume_map))


class DockerAddNetworkTest(AuthAPITestCase):
    def test_network_is_created_on_new_project(self):
        self.loginUser()
        # Create a new project
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        p: Project | None = Project.objects.filter(slug="zane-ops").first()
        self.assertIsNotNone(self.fake_docker_client.get_network(p))


class DockerRemoveNetworkTest(AuthAPITestCase):
    def test_network_is_deleted_on_archived_project(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)
        self.fake_docker_client.create_network(p)

        self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": p.slug})
        )

        self.assertIsNone(self.fake_docker_client.get_network(p))
        self.assertEqual(0, len(self.fake_docker_client.get_networks()))

    def test_with_nonexistent_network(self):
        owner = self.loginUser()
        p = Project.objects.create(slug="gh-clone", owner=owner)

        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "gh-clone"})
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        self.assertIsNone(self.fake_docker_client.get_network(p))


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

    def test_with_succesful_deploy(self):
        project, service = self.create_and_deploy_redis_docker_service()

        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(1, project_in_response.get("healthy_services"))
        self.assertEqual(1, project_in_response.get("total_services"))

    def test_with_failed_deployment(self):
        def create_raise_error(*args, **kwargs):
            raise Exception("Fake error")

        self.fake_docker_client.services.create = create_raise_error

        project, service = self.create_and_deploy_redis_docker_service()

        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(0, project_in_response.get("healthy_services"))
        self.assertEqual(1, project_in_response.get("total_services"))

    def test_with_unhealthy_deployment(self):
        project, service = self.create_and_deploy_redis_docker_service()

        # make the deployment unhealthy
        deployment: DockerDeployment = service.deployments.first()
        deployment.status = DockerDeployment.DeploymentStatus.UNHEALTHY
        deployment.save()

        response = self.client.get(reverse("zane_api:projects.list"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_in_response = response.json().get("results", [])[0]
        self.assertEqual(0, project_in_response.get("healthy_services"))
        self.assertEqual(1, project_in_response.get("total_services"))
