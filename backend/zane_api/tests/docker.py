from django.urls import reverse
from rest_framework import status

from .base import AuthAPITestCase, FakeDockerClient


class DockerViewTests(AuthAPITestCase):
    def setUp(self):
        super().setUp()
        self.loginUser()

    def test_search_docker_images(self):
        response = self.client.get(
            reverse("zane_api:docker.image_search"), QUERY_STRING="q=caddy"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)

        self.assertIsNotNone(response.json().get("images"))
        images = response.json().get("images")
        self.assertEqual(images[0]["full_image"], "caddy")
        self.assertEqual(images[1]["full_image"], "siwecos/caddy")

    def test_search_query_empty(self):
        response = self.client.get(reverse("zane_api:docker.image_search"))
        self.assertEqual(status.HTTP_400_BAD_REQUEST, response.status_code)


class DockerPortMappingViewTests(AuthAPITestCase):
    def test_successfull(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": 8082,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), True)

    def test_unavailable_port(self):
        self.loginUser()
        response = self.client.post(
            reverse("zane_api:docker.check_port_mapping"),
            data={
                "port": FakeDockerClient.PORT_USED_BY_HOST,
            },
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        self.assertEqual(response.json().get("available"), False)


#### Start of new tests for DeployDockerServiceAPIView ####
import pytest
from django.utils import timezone
from zane_api.models import Deployment, Service
from zane_api.temporal.workflows import DeployDockerServiceWorkflow
from zane_api.temporal.shared import CancelDeploymentSignalInput

@pytest.mark.django_db(transaction=True)
class TestDeployDockerServiceCancelPrevious(AuthAPITestCase):
    async def test_cancel_previous_true_workflow_started(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        # Ensure the service has no unapplied changes initially for a clean deploy
        await service.unapplied_changes.all().adelete()
        
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_wf_id_docker_deploy_old",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.docker_services.workflow_signal")
        # Mock start_workflow to prevent actual new deployment workflow
        mocker.patch("zane_api.views.docker_services.start_workflow") 

        url = reverse(
            "zane_api:services.docker.deploy_service", # Corrected view name
            kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": True, "commit_message": "New deploy"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK # This view returns 200 OK on success
        mock_workflow_signal.assert_called_once()
        
        args, kwargs = mock_workflow_signal.call_args
        assert kwargs["workflow"] == DeployDockerServiceWorkflow.run
        assert kwargs["signal"] == DeployDockerServiceWorkflow.cancel_deployment
        assert isinstance(kwargs["arg"], CancelDeploymentSignalInput)
        assert kwargs["arg"].deployment_hash == old_deployment.hash
        assert kwargs["workflow_id"] == old_deployment.workflow_id

        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_true_workflow_not_started(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        await service.unapplied_changes.all().adelete()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.QUEUED,
            started_at=None,
        )
        
        mocker.patch("zane_api.views.docker_services.start_workflow")

        url = reverse(
            "zane_api:services.docker.deploy_service",
             kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": True, "commit_message": "New deploy"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        await old_deployment.arefresh_from_db()
        assert old_deployment.status == Deployment.DeploymentStatus.CANCELLED
        assert "Cancelled due to new UI-triggered deployment." in old_deployment.status_reason
        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_false_workflow_started(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        await service.unapplied_changes.all().adelete()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_wf_id_docker_deploy_false",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.docker_services.workflow_signal")
        mocker.patch("zane_api.views.docker_services.start_workflow")

        url = reverse(
            "zane_api:services.docker.deploy_service",
            kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": False, "commit_message": "New deploy false"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        mock_workflow_signal.assert_not_called()
        await old_deployment.arefresh_from_db()
        assert old_deployment.status == Deployment.DeploymentStatus.STARTING
        assert await Deployment.objects.filter(service=service).acount() == 2

    async def test_cancel_previous_true_no_active_deployments(self, mocker):
        project, service = await self.acreate_docker_service_with_env()
        await service.unapplied_changes.all().adelete()
        await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.FAILED, # Non-active
            workflow_id="fake_wf_id_docker_deploy_failed",
            started_at=timezone.now(),
        )

        mock_workflow_signal = mocker.patch("zane_api.views.docker_services.workflow_signal")
        mocker.patch("zane_api.views.docker_services.start_workflow")

        url = reverse(
            "zane_api:services.docker.deploy_service",
            kwargs={
                "project_slug": project.slug,
                "env_slug": service.environment.name,
                "service_slug": service.slug,
            },
        )
        payload = {"cancel_previous_deployments": True, "commit_message": "New deploy no active"}
        response = await self.async_client.put(url, data=payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        mock_workflow_signal.assert_not_called()
        # One failed, one new queued
        assert await Deployment.objects.filter(service=service).acount() == 2 
        new_depl = await Deployment.objects.aget(service=service, status=Deployment.DeploymentStatus.QUEUED)
        assert new_depl is not None
#### End of new tests for DeployDockerServiceAPIView ####
