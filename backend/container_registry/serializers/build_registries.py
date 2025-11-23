from typing import cast
from rest_framework import serializers

from ..models import BuildRegistry
from temporal.workflows import DeployBuildRegistryWorkflow, UpdateBuildRegistryWorkflow
from temporal.client import TemporalClient
from temporal.shared import RegistryConfig, RegistrySnaphot, UpdateRegistryPayload
from django.db import transaction
import secrets
from django.db.models import Q, F, Value
from zane_api.validators import validate_url_domain
from rest_framework import pagination
import boto3
from botocore.exceptions import ClientError as S3Error


class BuildRegistryListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


class BuildRegistryListCreateSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(required=True)

    registry_domain = serializers.CharField(validators=[validate_url_domain])
    registry_username = serializers.CharField(default="zane")
    registry_password = serializers.CharField(write_only=True, required=False)

    def validate_is_global(self, is_global: bool):
        if not is_global and not BuildRegistry.objects.filter(is_global=True).exists():
            raise serializers.ValidationError(
                "At least one global build registry is required."
            )
        return is_global

    def validate(self, attrs: dict):
        password = attrs.get("registry_password")
        storage_backend = attrs.get("storage_backend")

        if password is None:
            attrs["registry_password"] = secrets.token_hex()

        print(f"{attrs=}")

        if storage_backend == BuildRegistry.StorageBackend.S3:
            s3_endpoint = attrs.get("s3_endpoint")
            s3_secure = attrs.get("s3_secure", True)
            s3_region = attrs.get("s3_region", "us-east-1")

            s3_bucket = attrs.get("s3_bucket")
            s3_access_key = attrs.get("s3_access_key")
            s3_secret_key = attrs.get("s3_secret_key")

            errors = {}
            if s3_bucket is None:
                errors["s3_bucket"] = ["This field is required"]
            if s3_access_key is None:
                errors["s3_access_key"] = ["This field is required"]
            if s3_secret_key is None:
                errors["s3_secret_key"] = ["This field is required"]

            if errors:
                raise serializers.ValidationError(errors)

            s3_config = {
                "aws_access_key_id": s3_access_key,
                "aws_secret_access_key": s3_secret_key,
                "region_name": s3_region,
            }
            if s3_endpoint is not None:
                s3_config["endpoint_url"] = s3_endpoint

                if not s3_secure:
                    s3_config["use_ssl"] = False

            s3 = boto3.client("s3", **s3_config)

            try:
                s3.head_bucket(Bucket=s3_bucket)
            except S3Error as e:
                raise serializers.ValidationError(
                    {"s3_bucket": [f"Unable to access bucket: {str(e)}"]}
                )

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        is_global = validated_data.get("is_global")

        if is_global:
            BuildRegistry.objects.update(is_global=False)

        registry = BuildRegistry.objects.create(**validated_data)

        registry.service_alias = BuildRegistry.generate_default_service_alias(registry)
        registry.swarm_service_name = BuildRegistry.generate_default_service_alias(
            registry
        )
        registry.save()

        def commit_callback():
            # TODO: s3

            config = RegistryConfig(
                storage=RegistryConfig.StorageConfig(
                    filesystem=RegistryConfig.StorageConfig.FilesystemDriver()
                    if registry.storage_backend == BuildRegistry.StorageBackend.LOCAL
                    else None
                )
            )
            payload = RegistrySnaphot(
                service_alias=cast(str, registry.service_alias),
                config=config,
                swarm_service_name=cast(str, registry.swarm_service_name),
                name=registry.name,
                id=registry.id,
                domain=registry.registry_domain,
                username=registry.registry_username,
                password=registry.registry_password,
                version=registry.version,
                is_secure=registry.is_secure,
            )

            TemporalClient.start_workflow(
                workflow=DeployBuildRegistryWorkflow.run,
                arg=payload,
                id=registry.workflow_id,
            )

        transaction.on_commit(commit_callback)

        return registry

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_global",
            "service_alias",
            "is_secure",
            "version",
            # credentials
            "registry_domain",
            "registry_username",
            "registry_password",
            # S3 credentials
            "s3_bucket",
            "s3_region",
            "s3_access_key",
            "s3_secret_key",
            "s3_endpoint",
            "s3_secure",
            "storage_backend",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "version": {"read_only": True},
            "service_alias": {"read_only": True},
            "s3_secret_key": {"write_only": True},
        }


class BuildRegistryUpdateDetailsSerializer(serializers.ModelSerializer):
    is_global = serializers.BooleanField(required=True)

    def validate_is_global(self, is_global: bool):
        self.instance = cast(BuildRegistry, self.instance)
        if (
            not is_global
            and not BuildRegistry.objects.filter(
                Q(is_global=True) & ~Q(pk=self.instance.id)
            ).exists()
        ):
            raise serializers.ValidationError(
                "At least one build registry must be set as the global registry."
            )
        return is_global

    @transaction.atomic()
    def update(self, instance: BuildRegistry, validated_data: dict):
        registry_domain = validated_data.get(
            "registry_domain", instance.registry_domain
        )
        registry_username = validated_data.get(
            "registry_username", instance.registry_username
        )
        registry_password = validated_data.get(
            "registry_password", instance.registry_password
        )
        registry_password = validated_data.get(
            "registry_password", instance.registry_password
        )

        name = validated_data.get("name", instance.name)
        is_global = validated_data.get("is_global", instance.is_global)
        is_secure = validated_data.get("is_secure", instance.is_secure)

        if is_global:
            BuildRegistry.objects.exclude(id=instance.id).update(is_global=False)

        BuildRegistry.objects.filter(pk=instance.id).update(
            registry_domain=registry_domain,
            name=name,
            is_global=is_global,
            is_secure=is_secure,
            registry_username=registry_username,
            registry_password=registry_password,
            version=F("version") + Value(1),
        )

        previous_config = RegistryConfig(
            storage=RegistryConfig.StorageConfig(
                filesystem=RegistryConfig.StorageConfig.FilesystemDriver()
                if instance.storage_backend == BuildRegistry.StorageBackend.LOCAL
                else None
            )
        )

        # TODO: update s3 config
        # new_config = RegistryConfig(
        #     storage=RegistryConfig.StorageConfig(
        #         filesystem=RegistryConfig.StorageConfig.FilesystemDriver()
        #         if instance.storage_backend == BuildRegistry.StorageBackend.LOCAL
        #         else None
        #     )
        # )

        previous_snapshot = RegistrySnaphot(
            service_alias=cast(str, instance.service_alias),
            swarm_service_name=cast(str, instance.swarm_service_name),
            id=instance.id,
            config=previous_config,
            name=instance.name,
            domain=instance.registry_domain,
            username=instance.registry_username,
            password=instance.registry_password,
            version=instance.version,
            is_secure=instance.is_secure,
        )
        new_snapshot = RegistrySnaphot(
            service_alias=cast(str, instance.service_alias),
            swarm_service_name=cast(str, instance.swarm_service_name),
            id=instance.id,
            config=previous_config,
            name=name,
            domain=registry_domain,
            username=registry_username,
            password=registry_password,
            version=instance.version + 1,
            is_secure=is_secure,
        )

        def commit_callback():
            payload = UpdateRegistryPayload(
                service_alias=cast(str, instance.service_alias),
                swarm_service_name=cast(str, instance.swarm_service_name),
                id=instance.id,
                previous=previous_snapshot,
                current=new_snapshot,
            )

            TemporalClient.start_workflow(
                workflow=UpdateBuildRegistryWorkflow.run,
                arg=payload,
                id=instance.workflow_id,
            )

        transaction.on_commit(commit_callback)

        instance.refresh_from_db()
        return instance

    class Meta:
        model = BuildRegistry
        fields = [
            "id",
            "name",
            "is_global",
            "registry_domain",
            "service_alias",
            "registry_username",
            "version",
            "is_secure",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "version": {"read_only": True},
            "service_alias": {"read_only": True},
            "registry_password": {"write_only": True},
        }
