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


from unittest.mock import patch # Moved to top with other imports
from django.utils import timezone # Moved to top
from zane_api.models import Deployment # Service is imported from .base
from zane_api.temporal.workflows import DeployDockerServiceWorkflow
from zane_api.temporal.shared import CancelDeploymentSignalInput
# Removed pytest, Service (as it's in base), ensured other necessary imports are at top or covered by base

class TestDeployDockerServiceCancelPrevious(AuthAPITestCase): 
    @patch("zane_api.views.docker_services.start_workflow") 
    @patch("zane_api.views.docker_services.workflow_signal") 
    async def test_cancel_previous_true_workflow_started(self, mock_workflow_signal, mock_start_workflow):
        project, service = await self.acreate_docker_service_with_env()
        # Ensure the service has no unapplied changes initially for a clean deploy
        await service.unapplied_changes.all().adelete()
        
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_wf_id_docker_deploy_old",
            started_at=timezone.now(),
        )

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_workflow_signal.assert_called_once()
        
        args, called_kwargs = mock_workflow_signal.call_args
        self.assertEqual(called_kwargs["workflow"], DeployDockerServiceWorkflow.run)
        self.assertEqual(called_kwargs["signal"], DeployDockerServiceWorkflow.cancel_deployment)
        self.assertIsInstance(called_kwargs["arg"], CancelDeploymentSignalInput)
        self.assertEqual(called_kwargs["arg"].deployment_hash, old_deployment.hash)
        self.assertEqual(called_kwargs["workflow_id"], old_deployment.workflow_id)

        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)

    @patch("zane_api.views.docker_services.start_workflow")
    # No need to mock workflow_signal if it's not expected to be called
    async def test_cancel_previous_true_workflow_not_started(self, mock_start_workflow):
        project, service = await self.acreate_docker_service_with_env()
        await service.unapplied_changes.all().adelete()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.QUEUED,
            started_at=None,
        )
        
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        await old_deployment.arefresh_from_db()
        self.assertEqual(old_deployment.status, Deployment.DeploymentStatus.CANCELLED)
        self.assertIn("Cancelled due to new UI-triggered deployment.", old_deployment.status_reason)
        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)

    @patch("zane_api.views.docker_services.start_workflow")
    @patch("zane_api.views.docker_services.workflow_signal")
    async def test_cancel_previous_false_workflow_started(self, mock_workflow_signal, mock_start_workflow):
        project, service = await self.acreate_docker_service_with_env()
        await service.unapplied_changes.all().adelete()
        old_deployment = await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.STARTING,
            workflow_id="fake_wf_id_docker_deploy_false",
            started_at=timezone.now(),
        )

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_workflow_signal.assert_not_called()
        await old_deployment.arefresh_from_db()
        self.assertEqual(old_deployment.status, Deployment.DeploymentStatus.STARTING)
        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)

    @patch("zane_api.views.docker_services.start_workflow")
    @patch("zane_api.views.docker_services.workflow_signal")
    async def test_cancel_previous_true_no_active_deployments(self, mock_workflow_signal, mock_start_workflow):
        project, service = await self.acreate_docker_service_with_env()
        await service.unapplied_changes.all().adelete()
        await Deployment.objects.acreate(
            service=service,
            status=Deployment.DeploymentStatus.FAILED, # Non-active
            workflow_id="fake_wf_id_docker_deploy_failed",
            started_at=timezone.now(),
        )

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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_workflow_signal.assert_not_called()
        # One failed, one new queued
        self.assertEqual(await Deployment.objects.filter(service=service).acount(), 2)
        new_depl = await Deployment.objects.aget(service=service, status=Deployment.DeploymentStatus.QUEUED)
        self.assertIsNotNone(new_depl)
#### End of new tests for DeployDockerServiceAPIView ####
