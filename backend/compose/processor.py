import re
from yaml import SafeDumper
import yaml
from typing import Dict, Any, List, cast
from django.core.exceptions import ValidationError
from .dtos import (
    ComposeStackSpec,
    ComposeServiceSpec,
    ComposeSpecDeploymentArtifacts,
    ComposeStackUrlRouteDto,
    ComposeStackEnvOverrideDto,
    ComposeVersionedConfig,
    ComposeConfigSpec,
)
from temporal.helpers import get_env_network_resource_name
import json
from django.conf import settings
from .models import ComposeStack, ComposeStackChange
import secrets
from zane_api.utils import (
    generate_random_chars,
    find_item_in_sequence,
)
from faker import Faker
import tempfile
import subprocess
import os
from expandvars import expand
from rest_framework import serializers
from zane_api.serializers import URLDomainField, URLPathField
from zane_api.models import URL, DeploymentURL
from container_registry.models import BuildRegistry
from django.db.models import Q
import uuid
import base64


class ComposeStackSpecSerializer(serializers.Serializer):
    x_zane_env = serializers.DictField(
        child=serializers.CharField(allow_blank=True), required=False
    )


class ComposeStackURLRouteSerializer(serializers.Serializer):
    domain = URLDomainField()
    base_path = URLPathField(default="/")
    strip_prefix = serializers.BooleanField(default=True)
    port = serializers.IntegerField(min_value=1)

    def validate(self, attrs: dict):
        if attrs["domain"] == settings.ZANE_APP_DOMAIN:
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where ZaneOps is installed is not allowed."
                    ]
                }
            )
        if attrs["domain"] == f"*.{settings.ZANE_APP_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the domain where ZaneOps is installed as a wildcard domain is not allowed."
                    ]
                }
            )
        if attrs["domain"] == f"*.{settings.ROOT_DOMAIN}":
            raise serializers.ValidationError(
                {
                    "domain": [
                        "Using the root domain as a wildcard is not allowed as it would shadow all the other services installed on ZaneOps."
                    ]
                }
            )

        if URL.objects.filter(
            Q(domain=attrs["domain"].lower()) & Q(base_path=attrs["base_path"].lower())
        ).exists():
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{attrs['domain']}` and base path `{attrs['base_path']}` "
                        f"is already assigned to another service."
                    ]
                }
            )

        if BuildRegistry.objects.filter(
            registry_domain=attrs["domain"].lower()
        ).exists():
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{attrs['domain']}` "
                        f"is already assigned to a build registry."
                    ]
                }
            )

        existing_deployment_urls = DeploymentURL.objects.filter(
            Q(domain=attrs["domain"].lower())
        ).distinct()
        if len(existing_deployment_urls) > 0:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{attrs['domain']}` is already assigned to another deployment."
                    ]
                }
            )

        domain = attrs["domain"]
        domain_parts = domain.split(".")
        domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)

        existing_parent_domain = URL.objects.filter(
            Q(domain=domain_as_wildcard.lower())
            & Q(base_path=attrs["base_path"].lower())
        ).distinct()
        if len(existing_parent_domain) > 0:
            raise serializers.ValidationError(
                {
                    "domain": (
                        f"URL with domain `{attrs['domain']}` cannot be used because it will be shadowed by the wildcard"
                        f" domain `{domain_as_wildcard}` which is already assigned to another service."
                    )
                }
            )

        if attrs.get("port") is None:
            raise serializers.ValidationError(
                {
                    "port": "To expose this service, you need to add an associated port to forward this URL to."
                }
            )

        # Check for conflicts with other compose stacks
        exclude_stack_id = self.context.get("exclude_stack_id")
        self._check_compose_stack_url_conflict(
            domain=attrs["domain"],
            base_path=attrs["base_path"],
            domain_as_wildcard=domain_as_wildcard,
            exclude_stack_id=exclude_stack_id,
        )

        return attrs

    def _check_compose_stack_url_conflict(
        self,
        domain: str,
        base_path: str,
        domain_as_wildcard: str,
        exclude_stack_id: str | None = None,
    ):
        """Check if the URL conflicts with any deployed compose stack URLs using raw SQL."""
        from django.db import connection

        # Build the exclusion clause
        exclude_clause = ""
        params = [domain.lower(), base_path.lower(), domain_as_wildcard.lower()]
        if exclude_stack_id:
            exclude_clause = "AND cs.id != %s"
            params.append(exclude_stack_id)

        # Use PostgreSQL's jsonb_each and jsonb_array_elements to search nested JSON
        # The urls field structure is: {service_name: [{domain, base_path, ...}, ...]}
        query = f"""
            SELECT cs.id
            FROM compose_composestack cs,
                 jsonb_each(cs.urls) AS services(service_name, routes),
                 jsonb_array_elements(services.routes) AS route
            WHERE cs.urls IS NOT NULL
              AND (
                  (lower(route->>'domain') = %s AND lower(route->>'base_path') = %s)
                  OR (lower(route->>'domain') = %s AND lower(route->>'base_path') = %s)
              )
              {exclude_clause}
            LIMIT 1
        """

        # Add base_path again for the wildcard check
        params = [
            domain.lower(),
            base_path.lower(),
            domain_as_wildcard.lower(),
            base_path.lower(),
        ]
        if exclude_stack_id:
            params.append(exclude_stack_id)

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()

        if result:
            raise serializers.ValidationError(
                {
                    "domain": [
                        f"URL with domain `{domain}` and base path `{base_path}` "
                        f"is already assigned to another compose stack."
                    ]
                }
            )


class ComposeStackURLRouteLabelsSerializer(serializers.Serializer):
    services = serializers.DictField(child=ComposeStackURLRouteSerializer())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pass context to child serializers
        exclude_stack_id = self.context.get("exclude_stack_id")
        if exclude_stack_id:
            self.fields["services"].child.context["exclude_stack_id"] = exclude_stack_id


class quoted(str):
    """class to represent string values that should be quoted in yaml"""

    pass


class ComposeSpecProcessor:
    """
    Processes user compose files into ZaneOps-compatible deployable compose files.

    Pipeline:
    1. User YAML → Parse to dict
    2. Validate structure and constraints
    3. Process template expressions ({{ generate_* }})
    4. Inject ZaneOps configuration (networks, labels, env vars)
    5. Convert to ComposeStackSpec dataclass → JSON (for storage)
    6. Convert back to YAML (for deployment)
    """

    # Template expression regex
    PASSWORD_REGEX = (
        r"generate_password[ \t]*\|[ \t]*(\d+)"  # format: generate_password | <number>
    )
    BASE64_REGEX = r"generate_base64[ \t]*\|[ \t]*(\".*\"|\'.*\')"  # format: generate_base64 | 'string'

    SUPPORTED_TEMPLATE_FUNCTIONS = [
        r"generate_slug",
        r"generate_domain",
        r"generate_username",
        r"generate_uuid",
        r"generate_email",
        PASSWORD_REGEX,
        BASE64_REGEX,
    ]

    @classmethod
    def _run_docker_validation(cls, content: str) -> str | None:
        """
        Run docker stack config validation on YAML content.

        Args:
            content: YAML content to validate

        Returns:
            Error message if validation fails, None if successful
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete_on_close=False
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()

            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    temp_file.name,
                    "config",
                ],
                capture_output=True,
                text=True,
            )

            return result.stderr.strip() if result.returncode != 0 else None

    @classmethod
    def validate_compose_file_syntax(cls, user_content: str):
        """
        Validate compose file using docker stack config.

        Args:
            user_content: Raw YAML content from user

        Raises:
            ValidationError: If docker stack config fails
        """
        # Run initial docker validation
        error = cls._run_docker_validation(user_content)

        if error:
            # If docker rejects inline config content, retry with file references
            # to ensure there are no other validation errors
            if error.endswith("Additional property content is not allowed"):
                user_spec_dict = cls._parse_user_yaml(user_content)

                # Replace config content with temporary file references
                for config in user_spec_dict.get("configs", {}).values():
                    if isinstance(config, dict) and "content" in config:
                        config["file"] = "./placeholder.conf"
                        del config["content"]

                # Retry validation with modified YAML
                retry_content = yaml.safe_dump(user_spec_dict, default_flow_style=False)
                retry_error = cls._run_docker_validation(retry_content)

                if retry_error:
                    raise ValidationError(f"Invalid compose file: {retry_error}")
            else:
                raise ValidationError(f"Invalid compose file: {error}")

        # Parse and validate YAML structure
        user_spec_dict = cls._parse_user_yaml(user_content)

        if not user_spec_dict.get("services"):
            raise ValidationError(
                "Invalid compose file: at least one service must be defined"
            )

        # Parse and validate `x-zane-env` section
        default_env = user_spec_dict.get("x-zane-env", {})
        if default_env:
            user_spec_dict["x_zane_env"] = default_env

        form = ComposeStackSpecSerializer(data=user_spec_dict)
        form.is_valid(raise_exception=True)

        # Validate services
        for name, service in user_spec_dict["services"].items():
            if not service.get("image"):
                raise ValidationError(
                    f"Invalid compose file: service '{name}' must have an 'image' field. Build from source is not supported."
                )

            service_spec = ComposeServiceSpec.from_dict({**service, "name": name})

            for volume in service_spec.volumes:
                if volume.type == "bind" and volume.source is not None:
                    if not os.path.isabs(volume.source):
                        raise ValidationError(
                            f"Invalid compose file: service '{name}' has a bind volume with relative source path '{volume.source}'. Only absolute paths are supported for bind mounts."
                        )

        # Validate configs use content instead of file
        for name, config in user_spec_dict.get("configs", {}).items():
            if config.get("file") is not None:
                raise ValidationError(
                    f"Invalid compose file: configs.{name} Additional property file is not allowed, please use config.content instead"
                )

    @classmethod
    def _parse_user_yaml(cls, content: str) -> Dict[str, Dict[str, Any]]:
        """
        Parse user YAML to dict.

        Raises:
            ValidationError: If YAML is invalid
        """
        try:
            parsed = yaml.safe_load(content)
            if parsed is None:
                raise ValidationError("Empty compose file")
            if not isinstance(parsed, dict):
                raise ValidationError("Compose file must be a YAML object/dictionary")
            return parsed
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML syntax: {str(e)}")

    @classmethod
    def _extract_template_expression(cls, env_value: str) -> str | None:
        """
        Extract template function name from environment variable value.

        Args:
            env_value: Environment variable value (may contain a template expression)

        Returns:
            Supported template function name if found (e.g., "generate_username"), None otherwise
        """
        patterns = "|".join(cls.SUPPORTED_TEMPLATE_FUNCTIONS)
        TEMPLATE_PATTERN = re.compile(rf"^\{{\{{[ \t]*({patterns})[ \t]*\}}\}}$")
        matched = TEMPLATE_PATTERN.match(str(env_value))

        if matched:
            return matched.group(1)
        return None

    @classmethod
    def _generate_template_value(cls, template_func: str, stack: ComposeStack) -> str:
        """
        Generate a random value for a template function.

        Args:
            template_func: Template function name (e.g., "generate_username")

        Returns:
            Generated random value
        """
        fake = Faker()

        match template_func:
            case "generate_domain":
                return f"{stack.project.slug}-{stack.slug}-{generate_random_chars(10)}.{settings.ROOT_DOMAIN}".lower()
            case "generate_slug":
                return fake.slug()
            case "generate_email":
                return fake.email()
            case "generate_uuid":
                return str(uuid.uuid4())
            case "generate_username":
                # Generate slug like "reddog65"
                adjective = fake.safe_color_name()
                noun = fake.free_email().split("@")[
                    0
                ]  # Extract username part from email
                number = fake.random_int(min=10, max=99)
                return f"{adjective}{noun}{number}"
            case template_func if template_func.startswith("generate_password"):
                # Cryptographically secure hex token
                regex = re.compile(cls.PASSWORD_REGEX)
                matched = cast(re.Match[str], regex.match(template_func))
                count = int(matched.group(1))

                if count >= 8 and count % 2 == 0:
                    return secrets.token_hex(int(count / 2))

                issues = []
                if count < 8:
                    issues.append(f"must be at least 8 characters (got {count})")
                if count % 2 != 0:
                    issues.append(f"must be an even number (got {count})")

                raise ValidationError(f"Invalid `{template_func}`: {', '.join(issues)}")
            case template_func if template_func.startswith("generate_base64"):
                regex = re.compile(cls.BASE64_REGEX)
                matched = cast(re.Match[str], regex.match(template_func))
                value = matched.group(1)

                return base64.b64encode(value[1:-1].encode()).decode()
            case _:
                raise ValidationError(
                    f"Unsupported template function `{template_func}`"
                )

    @classmethod
    def process_compose_spec(
        cls,
        user_content: str,
        stack: "ComposeStack",
        extra_env: Dict[str, str] | None = None,
    ) -> ComposeStackSpec:
        """
        Process user compose file into ZaneOps-compatible spec.

        Steps:
        1. Parse YAML
        2. Validate
        3. Merge environment variable overrides (which include generated values)
        4. Inject zane network
        5. Add ZaneOps tracking labels
        6. Add logging configuration
        7. Return ComposeStackSpec
        """

        # Parse YAML
        spec_dict = ComposeSpecProcessor._parse_user_yaml(user_content)

        # Convert to dataclass
        spec = ComposeStackSpec.from_dict(spec_dict)

        # Get environment network name
        env_network_name = get_env_network_resource_name(
            stack.environment_id,
            stack.project_id,
        )

        # Inject zane network & environment network to networks section
        if env_network_name not in spec.networks:
            spec.networks[env_network_name] = {
                "external": True,
            }

        if "zane" not in spec.networks:
            spec.networks["zane"] = {
                "external": True,
            }

        # Rename services to prevent DNS name collisions in the shared `zane` network
        # Since all stacks share the `zane` network, service names like `app` would collide
        # We prefix them with stack hash to ensure unique DNS names (e.g., abc123_app)
        renamed_services = {}
        for original_name, service in spec.services.items():
            hashed_name = f"{stack.hash_prefix}_{original_name}"
            service.name = hashed_name
            renamed_services[hashed_name] = service
        spec.services = renamed_services

        # Handle global env & overrides
        override_dict = {env.key: str(env.value) for env in stack.env_overrides.all()}

        pending_overrides = stack.unapplied_changes.filter(
            field=ComposeStackChange.ChangeField.ENV_OVERRIDES
        ).all()
        for change in pending_overrides:
            if change.type == ComposeStackChange.ChangeType.DELETE:
                old_value = cast(dict[str, str], change.old_value)
                override_dict.pop(old_value["key"], None)
            if change.type in [
                ComposeStackChange.ChangeType.UPDATE,
                ComposeStackChange.ChangeType.ADD,
            ]:
                new_value = cast(dict[str, str], change.new_value)
                override_dict[new_value["key"]] = new_value["value"]
                override_dict[new_value["key"]] = new_value["value"]
        if extra_env is not None:
            override_dict.update(extra_env)

        # generate temlate values
        for key, env in spec.envs.items():
            template_func = cls._extract_template_expression(env.value)

            if key in override_dict:
                env.value = override_dict[key]  # replace values with existing overrides
            elif template_func is not None:
                env.value = cls._generate_template_value(
                    template_func=template_func,
                    stack=stack,
                )
                env.is_newly_generated = True

            override_dict[key] = str(env.value)

        # expand all envs that are related to each-other
        for key, env in spec.envs.items():
            env.value = str(expand(str(env.value), environ=override_dict))

        # Process each service
        for service_name, service in spec.services.items():
            # Add zane & env networks with aliases
            original_service_name = service_name.removeprefix(f"{stack.hash_prefix}_")

            service.networks["zane"] = {
                "aliases": [f"{service_name}.{settings.ZANE_INTERNAL_DOMAIN}"]
            }
            # Add environment network with stable alias for cross-env communication
            # using the original service name and the stack alias prefix, for better UX
            service.networks[env_network_name] = {
                "aliases": [f"{stack.network_alias_prefix}-{original_service_name}"]
            }

            if service.networks.get("default") is None:
                service.networks["default"] = {}

            default_network_data = cast(dict, service.networks["default"])

            aliases: list[str] = default_network_data.get("aliases", [])

            if original_service_name not in aliases:
                aliases.append(original_service_name)
            service.networks["default"].update({"aliases": aliases})  # type: ignore

            # Add logging configuration (for Fluentd log collection)
            service.logging = {
                "driver": "fluentd",
                "options": {
                    "fluentd-address": settings.ZANE_FLUENTD_HOST,
                    "tag": json.dumps(
                        {
                            "zane.stack": stack.id,
                            "zane.service": service_name.removeprefix(
                                f"{stack.hash_prefix}_"
                            ),
                        }
                    ),
                    "fluentd-max-retries": "10",
                    "fluentd-sub-second-precision": "true",
                    # Non-blocking logging
                    "fluentd-async": "true",
                    "mode": "non-blocking",
                },
            }

            # Inject safe update_config for rolling updates
            if "update_config" not in service.deploy:
                service.deploy["update_config"] = {
                    "parallelism": 1,
                    "delay": "5s",
                    "order": "start-first",
                    "failure_action": "rollback",
                }

            # mode can be `replicated` | `global` or `replicated-job` | `global-job`
            if service.deploy.get("mode", "replicated") in ["replicated", "global"]:
                # 5. Set restart policy to "any" (unless user explicitly specified one)
                service.deploy["restart_policy"] = service.deploy.get(
                    "restart_policy", {"condition": "any"}
                )

            # Add ZaneOps tracking labels
            service.deploy["labels"] = service.deploy.get("labels", {})
            service.deploy["labels"].update(
                {
                    "zane-managed": "true",
                    "zane-project": stack.project_id,
                    "zane-environment": stack.environment_id,
                }
            )

            # update dependencies with hashed names
            service_dependencies = []
            for dependency in service.depends_on:
                hashed_name = f"{stack.hash_prefix}_{dependency}"
                if spec.services.get(hashed_name) is not None:
                    dependency = hashed_name
                service_dependencies.append(dependency)
            service.depends_on = service_dependencies

            # Disable healthcheck for services that don't have one
            if service.healthcheck is None:
                service.healthcheck = {"disable": True}

        # Add labels to volumes for tracking
        for _, volume_spec in spec.volumes.items():
            if not volume_spec.external:
                volume_spec.labels.update(
                    {
                        "zane-managed": "true",
                        "zane-stack": stack.id,
                        "zane-project": stack.project_id,
                    }
                )

        # Add labels to configs for tracking
        # renamed_configs = {}
        # all_configs: dict[str, str] = cast(dict, stack.configs) or {}
        for config_name, config in spec.configs.items():
            if not config.external:
                config.labels.update(
                    {
                        "zane-managed": "true",
                        "zane-stack": stack.id,
                        "zane-project": stack.project_id,
                    }
                )

            # renamed_configs[config_name] = config

            # process config `content` to `file` reference
            if config.content is not None:
                config.file = f"./{stack.hash_prefix}_{config_name}.conf"
                config.is_derived_from_content = True

        return spec

    @classmethod
    def _reconcile_computed_spec_with_user_content(
        cls,
        spec: ComposeStackSpec,
        user_content: str,
        stack_hash_prefix: str,
    ) -> Dict[str, Any]:
        # Parse YAML
        user_spec_dict = ComposeSpecProcessor._parse_user_yaml(user_content)

        compose_dict: Dict[str, Dict[str, Any]] = spec.to_dict()

        # Reconcile services with hashed names
        # The compose_dict has hashed service names (e.g., "abc123_app")
        # The user_spec_dict has original names (e.g., "app")
        # We need to map original names to hashed names during reconciliation
        reconciled_services = {}
        for original_name, user_service in user_spec_dict.get("services", {}).items():
            hashed_name = f"{stack_hash_prefix}_{original_name}"
            computed_service = compose_dict["services"].get(hashed_name, {})

            # Copy over user-specified fields that we didn't process
            for key, value in user_service.items():
                if computed_service.get(key) is None:
                    computed_service[key] = value
                if key == "environment":
                    envs = cast(dict[str, str], computed_service[key])
                    new_envs: dict[str, str] = {}
                    for k, v in envs.items():
                        if isinstance(v, bool):
                            v = "false"
                        new_envs[k] = quoted(v)  # always quote env variables
                    computed_service["environment"] = new_envs

            reconciled_services[hashed_name] = computed_service

        compose_dict["services"] = reconciled_services

        # Reconcile volumes with hashed names
        reconciled_volumes = {}
        for volume_name, user_volume in user_spec_dict.get("volumes", {}).items():
            computed_volume = compose_dict.get("volumes", {}).get(volume_name, {})

            # Copy over user-specified fields
            if isinstance(user_volume, dict):
                for key, value in user_volume.items():
                    if computed_volume.get(key) is None:
                        computed_volume[key] = value

            reconciled_volumes[volume_name] = computed_volume

        if reconciled_volumes:
            compose_dict["volumes"] = reconciled_volumes

        # include other keys that the user modified that we haven't processed yet
        for key, value in user_spec_dict.items():
            if compose_dict.get(key) is None:
                compose_dict[key] = value

        # remove empty keys
        compose_dict = {k: v for k, v in compose_dict.items() if v != {} and v != []}
        return compose_dict

    @classmethod
    def generate_deployable_yaml(
        cls,
        spec: ComposeStackSpec,
        user_content: str,
        stack_hash_prefix: str,
    ) -> str:
        """
        Convert ComposeStackSpec back to YAML for docker stack deploy,
        and also reconciliate with existing services.
        """
        # replace null values with empty
        # ex: data = {'deny': None, 'allow': None}
        #     =>
        # ```
        #  deny:
        #  allow:
        # ```
        # instead of
        # ```
        #  deny: null
        #  allow: null
        # ```
        SafeDumper.add_representer(
            type(None),
            lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
        )

        SafeDumper.add_representer(
            quoted,
            lambda dumper, data: dumper.represent_scalar(
                "tag:yaml.org,2002:str", data, style='"'
            ),
        )

        before = yaml.safe_dump(
            ComposeSpecProcessor._reconcile_computed_spec_with_user_content(
                spec,
                user_content,
                stack_hash_prefix,
            ),
            default_flow_style=False,
            sort_keys=False,  # Preserve order
            allow_unicode=True,
        )

        # always quote string characters to not confuse them with other value types
        expanded = expand(
            before,
            environ=spec.to_dict()["x-zane-env"],
        )

        return expanded

    @classmethod
    def extract_new_env_overrides(
        cls,
        spec: ComposeStackSpec,
    ) -> List[Dict[str, str]]:
        overrides = []

        for key, env in spec.envs.items():
            if env.is_newly_generated:
                overrides.append(
                    {
                        "key": key,
                        "value": env.value,
                    }
                )

        return overrides

    @classmethod
    def extract_config_contents(
        cls, spec: ComposeStackSpec, stack: "ComposeStack"
    ) -> Dict[str, "ComposeVersionedConfig"]:
        previous_configs = stack.configs or {}
        new_configs = {}

        for name, config in spec.configs.items():
            if config.is_derived_from_content and config.content is not None:
                expanded_content = expand(
                    config.content, environ=spec.to_dict()["x-zane-env"]
                )

                # Get previous version info
                previous_config = previous_configs.get(name)
                if previous_config is None:
                    # New config, start at version 1
                    new_configs[name] = ComposeVersionedConfig(
                        content=expanded_content, version=1
                    )
                else:
                    # Compare with previous version
                    prev_version_obj = ComposeVersionedConfig.from_dict(previous_config)
                    if prev_version_obj.content != expanded_content:
                        # Content changed, increment version
                        new_configs[name] = ComposeVersionedConfig(
                            content=expanded_content,
                            version=prev_version_obj.version + 1,
                        )
                    else:
                        # Content unchanged, keep same version
                        new_configs[name] = ComposeVersionedConfig(
                            content=expanded_content, version=prev_version_obj.version
                        )

        return new_configs

    @classmethod
    def validate_and_extract_service_urls(
        cls,
        spec: ComposeStackSpec,
        stack: "ComposeStack",
    ):
        """
        Extract URL routing configuration from service labels.

        Parses labels like:
        - zane.http.port: "80"
        - zane.http.routes.0.domain: "example.com"
        - zane.http.routes.0.base_path: "/"
        - zane.http.routes.0.strip_prefix: "false"

        Args:
            spec: The compose stack specification
            stack: The compose stack object (used for hash_prefix and to exclude
                   from conflict checks when updating)

        Returns:
            Dict mapping service names to list of route configs:
            {
                "web": [
                    {
                        "domain": "example.com",
                        "base_path": "/",
                        "strip_prefix": False,
                        "port": 80,
                    }
                ]
            }
        """
        service_urls: dict[str, List[ComposeStackUrlRouteDto]] = {}

        all_routes: List[dict[str, Any]] = []

        environ = spec.to_dict()["x-zane-env"]
        stack_hash_prefix = stack.hash_prefix

        for service_name, service in spec.services.items():
            if not service.deploy or not service.deploy.get("labels"):
                continue

            labels: Dict[str, str] = service.deploy["labels"]

            # Extract routes
            routes = []
            route_dict = {}

            for label in labels:
                domain_label_regex = re.compile(r"^zane\.http\.routes\.(\d+)\.domain$")

                matches = domain_label_regex.match(label)
                if matches is None:
                    continue

                route_index = matches.group(1)

                http_port = expand(
                    str(labels.get(f"zane.http.routes.{route_index}.port", "None")),
                    environ=environ,
                )

                domain = str(labels.get(f"zane.http.routes.{route_index}.domain"))
                base_path = str(
                    labels.get(f"zane.http.routes.{route_index}.base_path", "/").strip()
                )
                strip_prefix = str(
                    labels.get(f"zane.http.routes.{route_index}.strip_prefix", "true")
                ).lower()

                route: dict[str, Any] = {
                    "domain": expand(domain, environ=environ),
                    "base_path": expand(base_path, environ=environ),
                    "strip_prefix": expand(strip_prefix, environ=environ) == "true",
                    "port": http_port,
                }
                name = service_name.removeprefix(f"{stack_hash_prefix}_")
                key = f"{name}.deploy.labels.zane.http.routes.{route_index}"
                route_dict[key] = route

                existing_exact = find_item_in_sequence(
                    lambda r: (r["domain"] == route["domain"])
                    and r["base_path"] == route["base_path"],
                    all_routes,
                )
                if existing_exact:
                    raise serializers.ValidationError(
                        {
                            f"{key}.domain": f"Duplicate values for routes are not allowed, "
                            f"URL Route with domain `{route['domain']}` and base_path `{route['base_path']}` is already used by another service in the stack"
                        }
                    )

                all_routes.append(route)

            form = ComposeStackURLRouteLabelsSerializer(
                data={"services": route_dict},
                context={"exclude_stack_id": stack.id},
            )
            form.is_valid(raise_exception=True)

            routes = [
                ComposeStackUrlRouteDto(
                    domain=route["domain"],
                    base_path=route["base_path"],
                    strip_prefix=route["strip_prefix"],
                    port=int(route["port"]),
                )
                for route in route_dict.values()
            ]

            if routes:
                service_urls[service_name.removeprefix(f"{stack_hash_prefix}_")] = (
                    routes
                )

        for service, routes in service_urls.items():
            for route_index, url_route in enumerate(routes):
                domain = url_route.domain
                domain_parts = domain.split(".")
                domain_as_wildcard = domain.replace(domain_parts[0], "*", 1)
                existing_wildcard = find_item_in_sequence(
                    lambda r: (
                        r["domain"] == domain_as_wildcard
                        and r["base_path"] == url_route.base_path
                    ),
                    all_routes,
                )
                if existing_wildcard:
                    raise serializers.ValidationError(
                        {
                            f"{service}.deploy.labels.zane.http.routes.{route_index}.domain": f"Cannot use URL route with domain `{url_route.domain}` and base_path `{url_route.base_path}` "
                            f"as it will be shadowed by the wildcard `{domain_as_wildcard}` which already exists in the stack"
                        }
                    )

        return service_urls

    @classmethod
    def _apply_config_versioning_to_spec(
        cls,
        spec: ComposeStackSpec,
        config_versions: Dict[str, "ComposeVersionedConfig"],
        stack_hash_prefix: str,
    ) -> ComposeStackSpec:
        """
        Apply versioning to config names in the spec.
        All configs get renamed to {name}_v{version}.
        """
        # Create mapping of old names to new versioned names
        config_name_mapping: Dict[str, str] = {}
        renamed_configs: Dict[str, ComposeConfigSpec] = {}

        for config_name, config in spec.configs.items():
            version_info = config_versions.get(config_name)
            if version_info is not None:
                # Apply versioning (all configs are versioned starting from v1)
                new_name = f"{config_name}_v{version_info.version}"
                config_name_mapping[config_name] = new_name
                renamed_configs[new_name] = config
                # Update the file reference
                if config.is_derived_from_content:
                    config.file = f"./{stack_hash_prefix}_{new_name}.conf"
            else:
                # No version info (shouldn't happen), keep original name
                renamed_configs[config_name] = config

        spec.configs = renamed_configs

        # Update service config references
        for service in spec.services.values():
            updated_service_configs = []
            for service_config in service.configs:
                new_name = config_name_mapping.get(
                    service_config.source, service_config.source
                )
                service_config.source = new_name
                updated_service_configs.append(service_config)
            service.configs = updated_service_configs

        return spec

    @classmethod
    def compile_stack_for_deployment(
        cls, user_content: str, stack: "ComposeStack"
    ) -> ComposeSpecDeploymentArtifacts:
        """
        Process content, extract urls & env overrides
        """
        computed_spec = ComposeSpecProcessor.process_compose_spec(
            user_content=user_content,
            stack=stack,
        )

        # Extract configs with version info
        extracted_configs = ComposeSpecProcessor.extract_config_contents(
            spec=computed_spec, stack=stack
        )

        # Apply versioning to spec (rename configs if versions changed)
        computed_spec = ComposeSpecProcessor._apply_config_versioning_to_spec(
            spec=computed_spec,
            config_versions=extracted_configs,
            stack_hash_prefix=stack.hash_prefix,
        )

        computed_content = ComposeSpecProcessor.generate_deployable_yaml(
            spec=computed_spec,
            user_content=user_content,
            stack_hash_prefix=stack.hash_prefix,
        )

        extracted_service_routes = (
            ComposeSpecProcessor.validate_and_extract_service_urls(
                spec=computed_spec,
                stack=stack,
            )
        )

        extracted_envs = ComposeSpecProcessor.extract_new_env_overrides(
            spec=computed_spec
        )

        return ComposeSpecDeploymentArtifacts(
            computed_content=computed_content,
            computed_spec=yaml.safe_load(computed_content),
            configs=extracted_configs,
            urls=extracted_service_routes,
            env_overrides=[
                ComposeStackEnvOverrideDto.from_dict(env) for env in extracted_envs
            ],
        )
