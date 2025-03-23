import time
import django.db.transaction as transaction
from django.db import IntegrityError
from drf_spectacular.utils import (
    extend_schema,
    PolymorphicProxySerializer,
)
from faker import Faker
from rest_framework import status, exceptions
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.serializers import Serializer


from .base import (
    ResourceConflict,
)

from .serializers import (
    GitServiceDockerfileBuilderRequestSerializer,
    GitServiceBuilderRequestSerializer,
)
from ..models import (
    Project,
    Service,
    DeploymentChange,
    Environment,
)
from ..serializers import (
    ServiceSerializer,
    ErrorResponse409Serializer,
)

from ..utils import generate_random_chars


class CreateGitServiceAPIView(APIView):
    serializer_class = ServiceSerializer

    @extend_schema(
        request=PolymorphicProxySerializer(
            component_name="CreateGitServiceRequest",
            serializers=[GitServiceDockerfileBuilderRequestSerializer],
            resource_type_field_name="builder",
        ),
        responses={
            409: ErrorResponse409Serializer,
            201: ServiceSerializer,
        },
        operation_id="createDockerService",
        summary="Create a docker service",
        description="Create a service from a docker image.",
    )
    @transaction.atomic()
    def post(
        self,
        request: Request,
        project_slug: str,
        env_slug: str = Environment.PRODUCTION_ENV,
    ):
        try:
            project = Project.objects.get(slug=project_slug, owner=request.user)

            environment = Environment.objects.get(
                name=env_slug.lower(), project=project
            )
        except Project.DoesNotExist:
            raise exceptions.NotFound(
                f"A project with the slug `{project_slug}` does not exist"
            )
        except Environment.DoesNotExist:
            raise exceptions.NotFound(
                detail=f"An environment with the name `{env_slug}` does not exist in this project"
            )
        else:
            builder_serializer_map = {
                Service.Builder.DOCKERFILE: GitServiceDockerfileBuilderRequestSerializer
            }
            serializer = GitServiceBuilderRequestSerializer(data=request.data)
            if serializer.is_valid(raise_exception=True):
                buidler = serializer.data["builder"]
                form_serializer_class: type[Serializer] = builder_serializer_map[
                    buidler
                ]
                form = form_serializer_class(data=request.data)

                if form.is_valid(raise_exception=True):
                    data = form.data

                    # Create service in DB
                    fake = Faker()
                    Faker.seed(time.monotonic())
                    service_slug = data.get("slug", fake.slug()).lower()  # type: ignore
                    try:
                        service = Service.objects.create(
                            type=Service.ServiceType.GIT_REPOSITORY,
                            slug=service_slug,
                            project=project,
                            deploy_token=generate_random_chars(20),
                            environment=environment,
                        )
                    except IntegrityError:
                        raise ResourceConflict(
                            detail=f"A service with the slug `{service_slug}` already exists in this environment."
                        )
                    else:
                        service.network_alias = (
                            f"zn-{service.slug}-{service.unprefixed_id}"
                        )

                        source_data = {
                            "repository_url": data["repository_url"],  # type: ignore
                            "branch_name": data["branch_name"],  # type: ignore
                        }

                        match buidler:
                            case Service.Builder.DOCKERFILE:
                                source_data["dockerfile_builder_options"] = {
                                    "dockerfile_path": data["dockerfile_path"],  # type: ignore
                                    "build_context_dir": data["build_context_dir"],  # type: ignore
                                }
                            case _:
                                raise NotImplementedError(
                                    "This builder type has not yet been implemented"
                                )

                        DeploymentChange.objects.create(
                            field=DeploymentChange.ChangeField.SOURCE,
                            new_value=source_data,
                            type=DeploymentChange.ChangeType.UPDATE,
                            service=service,
                        )

                        service.save()

                    response = ServiceSerializer(service)
                    return Response(response.data, status=status.HTTP_201_CREATED)
