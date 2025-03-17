from .base import AuthAPITestCase
from django.urls import reverse
from rest_framework import status

from ..models import (
    Project,
    DockerDeployment,
    DockerRegistryService,
    ArchivedDockerService,
    Environment,
    DockerDeploymentChange,
    Volume,
    URL,
)
from ..temporal.activities import get_env_network_resource_name
from ..utils import jprint


class EnvironmentTests(AuthAPITestCase):
    def test_create_default_production_env_when_creating_project(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        self.assertEqual(1, Project.objects.count())
        project = Project.objects.get(slug="zane-ops")
        self.assertIsNotNone(project.environments.filter(name="production").first())

    async def test_create_production_network_when_creating_project(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        project = await Project.objects.aget(slug="zane-ops")

        production_env = (
            await project.environments.filter(name="production")
            .select_related("project")
            .afirst()
        )
        network = self.fake_docker_client.get_env_network(production_env)  # type: ignore
        self.assertIsNotNone(network)

    async def test_archive_project_removes_all_project_environments_networks(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        project = await Project.objects.aget(slug="zane-ops")

        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = await self.async_client.delete(
            reverse("zane_api:projects.details", kwargs={"slug": project.slug})
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        self.assertEqual(0, len(self.fake_docker_client.get_project_networks(project)))

    async def test_deploy_service_to_production_env_by_default(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        deployment: DockerDeployment = await service.deployments.afirst()  # type: ignore
        service = self.fake_docker_client.get_deployment_service(deployment=deployment)
        service_networks = {net["Target"]: net["Aliases"] for net in service.networks}  # type: ignore

        production_env = await p.aproduction_env
        self.assertTrue(
            get_env_network_resource_name(production_env.id, p.id) in service_networks
        )


class EnvironmentViewTests(AuthAPITestCase):
    def test_create_empty_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        staging_env = project.environments.filter(name="staging").first()
        self.assertIsNotNone(staging_env)

    def test_create_already_existing_env_should_cause_conflict_error(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "production"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    async def test_create_new_environment_should_also_create_network(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = await Project.objects.aget(slug="zane-ops")
        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        staging_env = await project.environments.aget(name="staging")

        network = self.fake_docker_client.get_env_network(staging_env)
        self.assertIsNotNone(network)

    def test_archive_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging"},
        )
        response = self.client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": "staging"},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)
        staging_env = project.environments.filter(name="staging").first()
        self.assertIsNone(staging_env)

    def test_rename_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging-oops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        staging_env = project.environments.get(name="staging-oops")
        response = self.client.patch(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": "staging-oops"},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        staging_env.refresh_from_db()
        self.assertEqual("staging", staging_env.name)

    def test_rename_environment_conflict_with_other_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        response = self.client.patch(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": "staging"},
            ),
            data={"name": "production"},
        )
        self.assertEqual(status.HTTP_409_CONFLICT, response.status_code)

    def test_cannot_rename_production_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")

        response = self.client.patch(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": "production"},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        production_env = project.environments.filter(name="production").first()
        self.assertIsNotNone(production_env)

    def test_cannot_archive_production_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = Project.objects.get(slug="zane-ops")
        response = self.client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": "production"},
            ),
        )
        self.assertEqual(status.HTTP_403_FORBIDDEN, response.status_code)
        production_env = project.environments.filter(name="production").first()
        self.assertIsNotNone(production_env)

    async def test_archiving_environment_also_delete_network(self):
        await self.aLoginUser()
        response = await self.async_client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        project = await Project.objects.aget(slug="zane-ops")
        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.create", kwargs={"slug": project.slug}
            ),
            data={"name": "staging"},
        )
        staging_env = await project.environments.aget(name="staging")

        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": project.slug, "env_slug": "staging"},
            ),
        )
        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        network = self.fake_docker_client.get_env_network(staging_env)
        self.assertIsNone(network)

    async def test_archiving_environment_also_archive_its_services(self):
        p, service = await self.acreate_redis_docker_service()

        response = await self.async_client.post(
            reverse("zane_api:projects.environment.create", kwargs={"slug": p.slug}),
            data={"name": "staging"},
        )

        staging_env = await p.environments.aget(name="staging")
        service.environment = staging_env
        await service.asave()

        response = await self.async_client.put(
            reverse(
                "zane_api:services.docker.deploy_service",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "env_slug": staging_env.name,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        first_deployment: DockerDeployment = await service.deployments.select_related("service").afirst()  # type: ignore

        response = await self.async_client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": p.slug, "env_slug": staging_env.name},
            ),
        )

        self.assertEqual(status.HTTP_204_NO_CONTENT, response.status_code)

        deleted_service: DockerRegistryService = await DockerRegistryService.objects.filter(slug=service.slug).afirst()  # type: ignore
        self.assertIsNone(deleted_service)

        archived_service: ArchivedDockerService = (
            await ArchivedDockerService.objects.filter(slug=service.slug).afirst()  # type: ignore
        )
        self.assertIsNotNone(archived_service)

        deleted_docker_service = self.fake_docker_client.get_deployment_service(
            first_deployment
        )
        self.assertIsNone(deleted_docker_service)
        deployments = [
            deployment
            async for deployment in DockerDeployment.objects.filter(
                service__slug=service.slug
            ).all()
        ]
        self.assertEqual(0, len(deployments))

    def test_archive_environment_with_non_deployed_service_deletes_the_service(self):
        p, service = self.create_redis_docker_service()

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env: Environment = p.environments.filter(name="staging").first()  # type: ignore

        response = self.client.delete(
            reverse(
                "zane_api:projects.environment.details",
                kwargs={"slug": p.slug, "env_slug": "staging"},
            ),
        )

        archived_service: ArchivedDockerService = ArchivedDockerService.objects.filter(
            environment_id=staging_env.id
        ).first()  # type: ignore
        self.assertIsNone(archived_service)


class CloneEnvironmentViewTests(AuthAPITestCase):
    def test_clone_environment_with_simple_service(self):
        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.SOURCE,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "image": "valkey/valkey:7.2-alpine",
                        "credentials": {
                            "username": "username",
                            "password": "password",
                        },
                    },
                ),
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.COMMAND,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value="redis-cli",
                ),
            ]
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env: Environment = p.environments.filter(name="staging").first()  # type: ignore
        self.assertIsNotNone(staging_env)

        services_in_staging = DockerRegistryService.objects.filter(
            environment=staging_env
        )
        self.assertEqual(1, services_in_staging.count())

        cloned_service: DockerRegistryService = services_in_staging.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        self.assertEqual(service.slug, cloned_service.slug)
        self.assertEqual(service.network_alias, cloned_service.network_alias)
        self.assertIsNotNone(cloned_service.deploy_token)

        self.assertEqual(2, cloned_service.unapplied_changes.count())
        source_change = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.SOURCE
        ).first()
        self.assertIsNotNone(source_change)

        cmd_change = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.COMMAND
        ).first()
        self.assertIsNotNone(cmd_change)

    def test_clone_environment_with_service_healthcheck(self):
        p, service = self.create_and_deploy_redis_docker_service(with_healthcheck=True)

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env = p.environments.get(name="staging")

        cloned_service: DockerRegistryService = staging_env.services.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        healthcheck_change = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.HEALTHCHECK
        ).first()
        self.assertIsNotNone(healthcheck_change)

    def test_clone_environment_with_service_resource_limits(self):
        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS,
                    type=DockerDeploymentChange.ChangeType.UPDATE,
                    new_value={
                        "cpus": 2,
                        "memory": {"value": 500, "unit": "MEGABYTES"},
                    },
                )
            ]
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env = p.environments.get(name="staging")

        cloned_service: DockerRegistryService = staging_env.services.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        change = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.RESOURCE_LIMITS
        ).first()
        self.assertIsNotNone(change)

    def test_clone_environment_with_service_volumes(self):
        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    type=DockerDeploymentChange.ChangeType.ADD,
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    new_value={
                        "container_path": "/data",
                        "name": "docker-volume",
                        "mode": Volume.VolumeMode.READ_WRITE,
                    },
                ),
                DockerDeploymentChange(
                    type=DockerDeploymentChange.ChangeType.ADD,
                    field=DockerDeploymentChange.ChangeField.VOLUMES,
                    new_value={
                        "container_path": "/var/run/docker.sock",
                        "host_path": "/var/run/docker.sock",
                        "mode": Volume.VolumeMode.READ_ONLY,
                        "name": "host-volume",
                    },
                ),
            ]
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env = p.environments.get(name="staging")

        cloned_service: DockerRegistryService = staging_env.services.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        volume_changes = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.VOLUMES
        )
        self.assertEqual(2, volume_changes.count())

    def test_clone_environment_with_service_urls(self):
        p, service = self.create_and_deploy_caddy_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.URLS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "domain": "dcr.fredkiss.dev",
                        "base_path": "/portainer",
                        "strip_prefix": True,
                        "associated_port": 8000,
                        "redirect_to": {
                            "url": "https://hello.fkss.me",
                        },
                    },
                )
            ]
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env = p.environments.get(name="staging")

        cloned_service: DockerRegistryService = staging_env.services.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        url_changes = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.URLS
        )
        self.assertEqual(1, url_changes.count())

        url_change = url_changes.first()
        first_url: URL = service.urls.filter(redirect_to__isnull=True).first()  # type: ignore

        # should change the domain for the URL
        self.assertNotEqual(first_url.domain, url_change.new_value.get("domain"))  # type: ignore
        self.assertEqual(first_url.base_path, url_change.new_value.get("base_path"))  # type: ignore
        self.assertEqual(first_url.associated_port, url_change.new_value.get("associated_port"))  # type: ignore
        self.assertEqual(first_url.strip_prefix, url_change.new_value.get("strip_prefix"))  # type: ignore
        # should only copy URLs that are not redirections
        self.assertIsNone(url_change.new_value.get("redirect_to"))  # type: ignore

    def test_clone_environment_with_service_ports_do_not_clone_the_ports(self):
        p, service = self.create_and_deploy_redis_docker_service(
            other_changes=[
                DockerDeploymentChange(
                    field=DockerDeploymentChange.ChangeField.PORTS,
                    type=DockerDeploymentChange.ChangeType.ADD,
                    new_value={
                        "host": 6379,
                        "forwarded": 6379,
                    },
                )
            ]
        )

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env = p.environments.get(name="staging")

        cloned_service: DockerRegistryService = staging_env.services.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        port_changes = cloned_service.unapplied_changes.filter(
            field=DockerDeploymentChange.ChangeField.PORTS
        )
        self.assertEqual(0, port_changes.count())

    async def test_clone_environment_with_deploy_body_should_create_resources(self):
        p, service = await self.acreate_and_deploy_redis_docker_service()

        response = await self.async_client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging", "deploy_services": True},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env: Environment = await p.environments.filter(name="staging").afirst()  # type: ignore
        self.assertIsNotNone(staging_env)

        services_in_staging = DockerRegistryService.objects.filter(
            environment=staging_env
        )
        self.assertEqual(1, await services_in_staging.acount())

        cloned_service: DockerRegistryService = await services_in_staging.afirst()  # type: ignore
        self.assertIsNotNone(cloned_service)

        cloned_service: DockerRegistryService = await staging_env.services.afirst()  # type: ignore
        self.assertEqual(1, await cloned_service.deployments.acount())

        self.assertEqual(0, await cloned_service.unapplied_changes.acount())

        cloned_deployment: DockerDeployment = await cloned_service.deployments.afirst()  # type: ignore
        swarm_service = self.fake_docker_client.get_deployment_service(
            cloned_deployment
        )
        self.assertIsNotNone(swarm_service)

    def test_clone_environment_with_service_url_with_deploy_body_should_create_deployment_url(
        self,
    ):
        p, service = self.create_and_deploy_caddy_docker_service()

        response = self.client.post(
            reverse(
                "zane_api:projects.environment.clone",
                kwargs={"slug": p.slug, "env_slug": Environment.PRODUCTION_ENV},
            ),
            data={"name": "staging", "deploy_services": True},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        jprint(response.json())

        staging_env: Environment = p.environments.filter(name="staging").first()  # type: ignore
        self.assertIsNotNone(staging_env)

        services_in_staging = DockerRegistryService.objects.filter(
            environment=staging_env
        )
        self.assertEqual(1, services_in_staging.count())

        cloned_service: DockerRegistryService = services_in_staging.first()  # type: ignore
        self.assertIsNotNone(cloned_service)

        cloned_service: DockerRegistryService = staging_env.services.first()  # type: ignore
        self.assertEqual(1, cloned_service.deployments.count())

        self.assertEqual(0, cloned_service.unapplied_changes.count())

        cloned_deployment: DockerDeployment = cloned_service.deployments.first()  # type: ignore
        count: int = cloned_deployment.urls.count()  # type: ignore wtf ???
        self.assertGreater(count, 0)


class ProjectEnvironmentViewTests(AuthAPITestCase):
    def test_filter_services_by_env(self):
        self.loginUser()
        self.create_caddy_docker_service()
        p, service = self.create_redis_docker_service()

        staging_env = p.environments.create(name="staging")
        service.environment = staging_env
        service.save()

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": p.slug, "env_slug": "production"},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        production_services = response.json()
        self.assertEqual(1, len(production_services))

        response = self.client.get(
            reverse(
                "zane_api:projects.service_list",
                kwargs={"slug": p.slug, "env_slug": "staging"},
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        staging_services = response.json()
        self.assertEqual(1, len(staging_services))

        self.assertNotEqual(production_services, staging_services)


class ServiceEnvironmentViewTests(AuthAPITestCase):
    def test_create_service_should_put_service_in_production_by_default(self):
        p, service = self.create_and_deploy_redis_docker_service()
        self.assertIsNotNone(service.environment)
        self.assertEqual(service.environment, p.production_env)

    def test_create_service_in_environment(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:projects.list"),
            data={"slug": "zane-ops"},
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)
        p = Project.objects.get(slug="zane-ops")
        p.environments.create(name="staging")

        create_service_payload = {"slug": "redis", "image": "valkey/valkey:7.2-alpine"}
        response = self.client.post(
            reverse(
                "zane_api:services.docker.create",
                kwargs={
                    "project_slug": p.slug,
                    "env_slug": "staging",
                },
            ),
            data=create_service_payload,
        )
        self.assertEqual(status.HTTP_201_CREATED, response.status_code)

        service = DockerRegistryService.objects.get(slug="redis")
        self.assertEqual("staging", service.environment.name)

    def test_get_service_in_environment(self):
        p, service = self.create_and_deploy_redis_docker_service()

        staging_env = p.environments.create(name="staging")
        service.environment = staging_env
        service.save()

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "env_slug": "production",
                },
            ),
        )
        jprint(response.json())
        self.assertEqual(status.HTTP_404_NOT_FOUND, response.status_code)

        response = self.client.get(
            reverse(
                "zane_api:services.docker.details",
                kwargs={
                    "project_slug": p.slug,
                    "service_slug": service.slug,
                    "env_slug": staging_env.name,
                },
            ),
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
