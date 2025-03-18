from .base import AuthAPITestCase
from ..models import Project, DockerRegistryService, Environment
from django.urls import reverse
from rest_framework import status


class ResourceSearchViewTests(AuthAPITestCase):
    def test_filter_query(self):
        owner = self.loginUser()

        projects = Project.objects.bulk_create(
            [
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
                Project(owner=owner, slug="zaneops"),
            ]
        )
        Environment.objects.bulk_create(
            [Environment(project=p, name="production") for p in projects]
        )

        DockerRegistryService.objects.bulk_create(
            [
                DockerRegistryService(
                    project=projects[0],
                    slug="gh-clone",
                    environment=projects[0].production_env,
                ),
                DockerRegistryService(
                    project=projects[1],
                    slug="gh-next",
                    environment=projects[1].production_env,
                ),
                DockerRegistryService(
                    project=projects[2],
                    slug="zaneops",
                    environment=projects[2].production_env,
                ),
            ]
        )

        response = self.client.get(
            reverse("zane_api:resources.search"), QUERY_STRING="query=gh"
        )
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json()
        self.assertEqual(4, len(project_list))

    def test_filter_no_query(self):
        owner = self.loginUser()

        projects = Project.objects.bulk_create(
            [
                Project(owner=owner, slug="gh-clone"),
                Project(owner=owner, slug="gh-next"),
                Project(owner=owner, slug="zaneops"),
            ]
        )
        Environment.objects.bulk_create(
            [Environment(project=p, name="production") for p in projects]
        )

        DockerRegistryService.objects.bulk_create(
            [
                DockerRegistryService(
                    project=projects[0],
                    slug="gh-clone",
                    environment=projects[0].production_env,
                ),
                DockerRegistryService(
                    project=projects[1],
                    slug="gh-next",
                    environment=projects[1].production_env,
                ),
                DockerRegistryService(
                    project=projects[2],
                    slug="zaneops",
                    environment=projects[2].production_env,
                ),
            ]
        )

        response = self.client.get(reverse("zane_api:resources.search"))
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        project_list = response.json()
        self.assertEqual(6, len(project_list))
