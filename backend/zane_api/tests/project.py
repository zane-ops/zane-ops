from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase
from ..docker_operations import get_docker_service_resource_name
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
)


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
        owner = self.loginUser()
        p = Project.objects.create(slug="sandbox", owner=owner)

        create_service_payload = {
            "slug": "gitea",
            "image": "gitea/gitea:latest",
            "urls": [{"domain": "gitea.zane.local", "base_path": "/"}],
            "ports": [{"forwarded": 3000}],
            "env": {"USER_UID": "1000", "USER_GID": "1000"},
            "volumes": [{"name": "gitea", "mount_path": "/data"}],
        }

        # create the service
        self.client.post(
            reverse("zane_api:services.docker.create", kwargs={"project_slug": p.slug}),
            data=create_service_payload,
            content_type="application/json",
        )

        # then archive the project
        response = self.client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": "sandbox"})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        # Service is deleted
        deleted_service = DockerRegistryService.objects.filter(slug="gitea").first()
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            ArchivedDockerService.objects.filter(slug="gitea")
            .prefetch_related("volumes")
            .prefetch_related("env_variables")
            .prefetch_related("ports")
            .prefetch_related("urls")
        ).first()
        self.assertIsNotNone(archived_service)

        # Deployments are cleaned up
        deployments = DockerDeployment.objects.filter(service__slug="gitea")
        self.assertEqual(0, len(deployments))

        # Volumes are cleaned up
        deleted_volumes = Volume.objects.filter(name="gitea")
        self.assertEqual(0, len(deleted_volumes))
        self.assertEqual(1, len(archived_service.volumes.all()))

        # env variables are cleaned up
        deleted_envs = DockerEnvVariable.objects.filter(service__slug="cache-db")
        self.assertEqual(0, len(deleted_envs))
        self.assertEqual(2, len(archived_service.env_variables.all()))

        # ports are cleaned up
        deleted_ports = PortConfiguration.objects.filter(host=6383)
        self.assertEqual(0, len(deleted_ports))
        self.assertEqual(1, len(archived_service.ports.all()))

        # urls are cleaned up
        deleted_urls = URL.objects.filter(domain="gitea.zane.local", base_path="/")
        self.assertEqual(0, len(deleted_urls))
        self.assertEqual(1, len(archived_service.urls.all()))

        # --- Docker Resources ---
        # service is removed
        deleted_docker_service = self.fake_docker_client.service_map.get(
            get_docker_service_resource_name(
                project_id=p.id, service_id=archived_service.original_id
            )
        )
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
    def test_get_statuses_empty(self):
        owner = self.loginUser()

        thullo = Project.objects.create(owner=owner, slug="thullo")

        query_string = f"ids={thullo.id}"
        response = self.client.get(
            reverse("zane_api:projects.status_list"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        statuses = response.json().get("projects", {})
        is_status_list_not_empty = bool(statuses)
        self.assertTrue(is_status_list_not_empty)
        self.assertIsNotNone(statuses.get(thullo.id))
        thullo_status = statuses.get(thullo.id)
        self.assertEqual(0, thullo_status.get("healthy_services"))
        self.assertEqual(0, thullo_status.get("unhealthy_services"))

    def test_with_succesful_deploy(self):
        owner = self.loginUser()

        sandbox = Project.objects.create(owner=owner, slug="sandbox")

        # Creat service
        create_service_payload = {
            "slug": "redis",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": sandbox.slug}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        query_string = f"ids={sandbox.id}"
        response = self.client.get(
            reverse("zane_api:projects.status_list"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        statuses = response.json().get("projects", {})

        self.assertIsNotNone(statuses.get(sandbox.id))
        project_status = statuses.get(sandbox.id)
        self.assertEqual(1, project_status.get("healthy_services"))
        self.assertEqual(0, project_status.get("unhealthy_services"))

    def test_with_multiple_projects(self):
        owner = self.loginUser()

        sandbox = Project.objects.create(owner=owner, slug="sandbox")
        sandbox2 = Project.objects.create(owner=owner, slug="sandbox-2")

        # Creat service
        create_service_payload = {
            "slug": "redis",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": sandbox.slug}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        query_string = f"ids={sandbox.id}&ids={sandbox2.id}"
        response = self.client.get(
            reverse("zane_api:projects.status_list"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        statuses = response.json().get("projects", {})
        self.assertEqual(
            {
                sandbox.id: {"healthy_services": 1, "unhealthy_services": 0},
                sandbox2.id: {"healthy_services": 0, "unhealthy_services": 0},
            },
            statuses,
        )

    def test_with_failed_deployment(self):
        owner = self.loginUser()

        sandbox = Project.objects.create(owner=owner, slug="sandbox")

        # Create service
        create_service_payload = {
            "slug": "redis",
            "image": "redis:alpine",
        }

        def create_raise_error(*args, **kwargs):
            raise Exception("Fake error")

        self.fake_docker_client.services.create = create_raise_error

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": sandbox.slug}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        query_string = f"ids={sandbox.id}"
        response = self.client.get(
            reverse("zane_api:projects.status_list"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        statuses = response.json().get("projects", {})

        self.assertIsNotNone(statuses.get(sandbox.id))
        project_status = statuses.get(sandbox.id)

        self.assertEqual(0, project_status.get("healthy_services"))
        self.assertEqual(1, project_status.get("unhealthy_services"))

    def test_with_unhealthy_deployment(self):
        owner = self.loginUser()

        sandbox = Project.objects.create(owner=owner, slug="sandbox")

        # Create service
        create_service_payload = {
            "slug": "redis",
            "image": "redis:alpine",
        }

        response = self.client.post(
            reverse(
                "zane_api:services.docker.create", kwargs={"project_slug": sandbox.slug}
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        # make the deployment unhealthy
        deployment: DockerDeployment = DockerDeployment.objects.filter(
            service__slug="redis"
        ).first()
        deployment.status = DockerDeployment.DeploymentStatus.UNHEALTHY
        deployment.save()

        query_string = f"ids={sandbox.id}"
        response = self.client.get(
            reverse("zane_api:projects.status_list"), QUERY_STRING=query_string
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        statuses = response.json().get("projects", {})
        self.assertIsNotNone(statuses.get(sandbox.id))
        project_status = statuses.get(sandbox.id)

        self.assertEqual(0, project_status.get("healthy_services"))
        self.assertEqual(1, project_status.get("unhealthy_services"))
