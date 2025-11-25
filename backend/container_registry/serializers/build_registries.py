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
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.client import Config
from zane_api.models import URL, DeploymentChange


class BuildRegistryListPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "per_page"
    page_query_param = "page"


class S3CredentialsSerializer(serializers.Serializer):
    region = serializers.CharField(
        max_length=50,
        default="us-east-1",
    )
    endpoint = serializers.URLField(required=False)
    secure = serializers.BooleanField(default=True)

    bucket = serializers.CharField(required=True)
    access_key = serializers.CharField(required=True)
    secret_key = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        parent_instance: BuildRegistry | None = self.context.get("parent_instance")

        # Get values with proper fallback to defaults or existing instance values
        if parent_instance and parent_instance.s3_credentials:
            # Fallback to existing credentials if not provided in update
            existing = parent_instance.s3_credentials
            region = attrs.get("region", existing.get("region", "us-east-1"))
            secure = attrs.get("secure", existing.get("secure", True))
            endpoint = attrs.get("endpoint", existing.get("endpoint"))
            bucket = attrs.get("bucket", existing.get("bucket"))
            access_key = attrs.get("access_key", existing.get("access_key"))
            secret_key = attrs.get("secret_key", existing.get("secret_key"))
        else:
            # Use field defaults for new credentials
            region = attrs.get("region", "us-east-1")
            secure = attrs.get("secure", True)
            endpoint = attrs.get("endpoint")
            bucket = attrs.get("bucket")
            access_key = attrs.get("access_key")
            secret_key = attrs.get("secret_key")

        # Validate required fields
        errors = {}
        if not bucket:
            errors["bucket"] = "This field is required"
        if not access_key:
            errors["access_key"] = "This field is required"
        if not secret_key:
            errors["secret_key"] = "This field is required"

        if errors:
            raise serializers.ValidationError(errors)

        # Update attrs with resolved values
        attrs["region"] = region
        attrs["secure"] = secure
        if endpoint is not None:
            attrs["endpoint"] = endpoint

        # Build boto3 config
        config = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
        }

        if endpoint is not None:
            config["endpoint_url"] = endpoint
            if not secure:
                config["use_ssl"] = False

        # Test S3 connection
        try:
            s3 = boto3.client("s3", config=Config(signature_version="s3v4"), **config)
            s3.head_bucket(Bucket=bucket)
        except ClientError as e:
            error_code = str(e.response.get("Error", {}).get("Code", "Unknown"))
            errors = {}

            # Provide specific error messages based on error type
            if error_code == "404" or error_code == "NoSuchBucket":
                errors["bucket"] = (
                    f"Bucket '{bucket}' does not exist or is not accessible. "
                    f"Error details: {str(e)}"
                )
            elif error_code == "403" or error_code == "AccessDenied":
                errors["access_key"] = errors["secret_key"] = (
                    f"Access denied. Please verify your access key and secret key have "
                    f"the necessary permissions to access this bucket. "
                    f"Error details: {str(e)}"
                )
            elif error_code == "InvalidAccessKeyId":
                errors["access_key"] = (
                    f"Invalid access key ID. Please check that your access key is correct. "
                    f"Error details: {str(e)}"
                )
            elif error_code == "SignatureDoesNotMatch":
                errors["secret_key"] = (
                    f"Invalid secret key. The signature does not match. "
                    f"Please verify your secret key is correct. "
                    f"Error details: {str(e)}"
                )
            else:
                errors["bucket"] = errors["access_key"] = errors["secret_key"] = (
                    f"Unable to connect to S3 bucket. Please verify all credentials are correct. "
                    f"Error details: {str(e)}"
                )

            raise serializers.ValidationError(errors)
        except EndpointConnectionError:
            raise serializers.ValidationError(
                {
                    "endpoint": f"Cannot connect to endpoint '{endpoint}'. Please verify the endpoint URL is correct."
                }
            )
        except Exception as e:
            # Catch any other unexpected errors
            raise serializers.ValidationError(f"S3 validation failed: {str(e)}")

        return attrs


class BuildRegistryListCreateSerializer(serializers.ModelSerializer):
    is_default = serializers.BooleanField(required=True)

    registry_domain = serializers.CharField(validators=[validate_url_domain])
    registry_username = serializers.CharField(default="zane")
    registry_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    s3_credentials = S3CredentialsSerializer(required=False)

    def validate_registry_domain(self, domain: str):
        assigned_to_service = URL.objects.filter(
            Q(domain=domain) | Q(domain=f"*.{domain}")
        ).exists()
        assigning_to_service = DeploymentChange.objects.filter(
            Q(
                field=DeploymentChange.ChangeField.URLS,
                applied=False,
            )
            & (Q(new_value__domain=domain) | Q(new_value__domain=f"*.{domain}")),
        ).exists()

        if assigned_to_service or assigning_to_service:
            raise serializers.ValidationError(
                "Cannot use this domain as it is already assigned to a service."
            )

        return domain

    def validate_is_default(self, is_default: bool):
        if (
            not is_default
            and not BuildRegistry.objects.filter(is_default=True).exists()
        ):
            raise serializers.ValidationError(
                "At least one build registry must be set as the default registry."
            )
        return is_default

    def validate(self, attrs: dict):
        password = attrs.get("registry_password")
        storage_backend = attrs.get("storage_backend")

        if not password:
            attrs["registry_password"] = secrets.token_hex()

        if storage_backend == BuildRegistry.StorageBackend.LOCAL:
            # remove s3 credentials
            attrs.pop("s3_credentials", None)

        if (
            storage_backend == BuildRegistry.StorageBackend.S3
            and attrs.get("s3_credentials") is None
        ):
            errors = {
                "bucket": "This field is required",
                "access_key": "This field is required",
                "secret_key": "This field is required",
            }

            raise serializers.ValidationError({"s3_credentials": errors})

        return attrs

    @transaction.atomic()
    def create(self, validated_data: dict):
        is_default = validated_data.get("is_default")

        if is_default:
            BuildRegistry.objects.update(is_default=False)

        registry = BuildRegistry.objects.create(**validated_data)

        registry.service_alias = BuildRegistry.generate_default_service_alias(registry)
        registry.swarm_service_name = BuildRegistry.generate_default_service_alias(
            registry
        )
        registry.save()

        def commit_callback():
            fs_config = None
            if registry.storage_backend == BuildRegistry.StorageBackend.LOCAL:
                fs_config = RegistryConfig.StorageConfig.Filesystem()

            s3_config = None
            if (
                registry.storage_backend == BuildRegistry.StorageBackend.S3
                and registry.s3_credentials is not None
            ):
                credentials = cast(dict, registry.s3_credentials)
                s3_config = RegistryConfig.StorageConfig.S3(
                    bucket=credentials["bucket"],
                    accesskey=credentials["access_key"],
                    secretkey=credentials["secret_key"],
                    region=credentials["region"],
                    regionendpoint=credentials["endpoint"],
                )

            config = RegistryConfig(
                storage=RegistryConfig.StorageConfig(
                    filesystem=fs_config,
                    s3=s3_config,
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
            "is_default",
            "service_alias",
            "is_secure",
            "version",
            # credentials
            "registry_domain",
            "registry_username",
            "registry_password",
            # S3 credentials
            "s3_credentials",
            "storage_backend",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "version": {"read_only": True},
            "service_alias": {"read_only": True},
        }


class BuildRegistryUpdateDetailsSerializer(serializers.ModelSerializer):
    is_default = serializers.BooleanField(required=True)

    s3_credentials = S3CredentialsSerializer(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pass instance to nested serializer via context
        if self.instance and "s3_credentials" in self.fields:
            self.fields["s3_credentials"].context["parent_instance"] = self.instance

    def validate_registry_domain(self, domain: str):
        assigned_to_service = URL.objects.filter(
            Q(domain=domain) | Q(domain=f"*.{domain}")
        ).exists()
        assigning_to_service = DeploymentChange.objects.filter(
            Q(
                field=DeploymentChange.ChangeField.URLS,
                applied=False,
            )
            & (Q(new_value__domain=domain) | Q(new_value__domain=f"*.{domain}")),
        ).exists()

        if assigned_to_service or assigning_to_service:
            raise serializers.ValidationError(
                "Cannot use this domain as it is already assigned to a service."
            )

        return domain

    def validate_is_default(self, is_default: bool):
        self.instance = cast(BuildRegistry, self.instance)
        if (
            not is_default
            and not BuildRegistry.objects.filter(
                Q(is_default=True) & ~Q(pk=self.instance.id)
            ).exists()
        ):
            raise serializers.ValidationError(
                "At least one build registry must be set as the default registry."
            )
        return is_default

    def validate(self, attrs: dict):
        storage_backend = attrs.get("storage_backend", self.instance.storage_backend)
        s3_credentials = attrs.get("s3_credentials", self.instance.s3_credentials)

        if storage_backend == BuildRegistry.StorageBackend.LOCAL:
            # remove s3 credentials
            attrs.pop("s3_credentials", None)
        if (
            storage_backend == BuildRegistry.StorageBackend.S3
            and s3_credentials is None
        ):
            raise serializers.ValidationError(
                {"s3_credentials": "Please provide s3 credentials"}
            )

        return attrs

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
        storage_backend = validated_data.get(
            "storage_backend", instance.storage_backend
        )
        s3_credentials = validated_data.get("s3_credentials", instance.s3_credentials)

        name = validated_data.get("name", instance.name)
        is_default = validated_data.get("is_default", instance.is_default)
        is_secure = validated_data.get("is_secure", instance.is_secure)

        if is_default:
            BuildRegistry.objects.exclude(id=instance.id).update(is_default=False)

        BuildRegistry.objects.filter(pk=instance.id).update(
            version=F("version") + Value(1),
            registry_domain=registry_domain,
            name=name,
            is_default=is_default,
            is_secure=is_secure,
            registry_username=registry_username,
            registry_password=registry_password,
            storage_backend=storage_backend,
            s3_credentials=s3_credentials,
        )

        def get_storage_config(storage_backend: str, s3_credentials: dict | None):
            fs_config = None
            if storage_backend == BuildRegistry.StorageBackend.LOCAL:
                fs_config = RegistryConfig.StorageConfig.Filesystem()

            s3_config = None
            if (
                storage_backend == BuildRegistry.StorageBackend.S3
                and s3_credentials is not None
            ):
                s3_config = RegistryConfig.StorageConfig.S3(
                    bucket=s3_credentials["bucket"],
                    accesskey=s3_credentials["access_key"],
                    secretkey=s3_credentials["secret_key"],
                    region=s3_credentials["region"],
                    regionendpoint=s3_credentials["endpoint"],
                )
            return RegistryConfig.StorageConfig(filesystem=fs_config, s3=s3_config)

        previous_snapshot = RegistrySnaphot(
            service_alias=cast(str, instance.service_alias),
            swarm_service_name=cast(str, instance.swarm_service_name),
            id=instance.id,
            config=RegistryConfig(
                storage=get_storage_config(
                    instance.storage_backend,
                    instance.s3_credentials,
                )
            ),
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
            config=RegistryConfig(
                storage=get_storage_config(
                    storage_backend,
                    s3_credentials,
                )
            ),
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
            "is_default",
            "registry_domain",
            "service_alias",
            "registry_username",
            "registry_password",
            "version",
            "is_secure",
            "storage_backend",
            # S3 credentials
            "s3_credentials",
        ]
        extra_kwargs = {
            "id": {"read_only": True},
            "version": {"read_only": True},
            "service_alias": {"read_only": True},
            "registry_password": {"write_only": True},
        }
