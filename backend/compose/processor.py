import re
from yaml import SafeDumper
import yaml
from typing import Dict, Any, List, cast
from django.core.exceptions import ValidationError
from .dtos import ComposeStackSpec, ComposeServiceSpec
from temporal.helpers import get_env_network_resource_name
import json
from django.conf import settings
from .models import ComposeStack
import secrets
from zane_api.utils import (
    generate_random_chars,
    replace_placeholders,
)
from faker import Faker
import tempfile
import subprocess
import os
from expandvars import expand
from rest_framework import serializers
from zane_api.serializers import URLDomainField, URLPathField


class ComposeStackSpecSerializer(serializers.Serializer):
    x_env = serializers.DictField(child=serializers.CharField(), required=False)


class ComposeStackURLRouteSerializer(serializers.Serializer):
    domain = URLDomainField()
    base_path = URLPathField(default="/")
    strip_prefix = serializers.BooleanField(default=True)
    port = serializers.IntegerField(min_value=1)


class ComposeStackURLRouteLabelsSerializer(serializers.Serializer):
    services = serializers.DictField(child=ComposeStackURLRouteSerializer())


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

    SUPPORTED_TEMPLATE_FUNCTIONS = [
        "generate_username",
        "generate_random_slug",
        "generate_secure_password",
        "generate_random_chars_32",
        "generate_random_chars_64",
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
                ["docker", "stack", "config", "-c", temp_file.name],
                capture_output=True,
                text=True,
            )

            return result.stderr.strip() if result.returncode != 0 else None

    @classmethod
    def validate_compose_file(cls, user_content: str):
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

        # Parse and validate `x-env` section
        default_env = user_spec_dict.get("x-env", {})
        if default_env:
            user_spec_dict["x_env"] = default_env

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
                    f"Invalid compose file: configs.{name} Additional property content is not allowed, please use config.content instead"
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
        TEMPLATE_PATTERN = re.compile(r"^\{\{[ \t]*(\w+)[ \t]*\}\}$")
        match = TEMPLATE_PATTERN.match(str(env_value))

        if match:
            func_name = match.group(1)
            return func_name if func_name in cls.SUPPORTED_TEMPLATE_FUNCTIONS else None
        return None

    @classmethod
    def _generate_template_value(cls, template_func: str) -> str:
        """
        Generate a random value for a template function.

        Args:
            template_func: Template function name (e.g., "generate_username")

        Returns:
            Generated random value
        """
        fake = Faker()

        match template_func:
            case "generate_username":
                # Generate slug like "reddog65"
                adjective = fake.safe_color_name()
                noun = fake.free_email().split("@")[
                    0
                ]  # Extract username part from email
                number = fake.random_int(min=10, max=99)
                return f"{adjective}{noun}{number}"
            case "generate_random_slug":
                return fake.slug()
            case "generate_secure_password":
                # Cryptographically secure 64-char hex token
                return secrets.token_hex(32)
            case "generate_random_chars_32":
                # Generate 32 random alphanumeric chars
                return generate_random_chars(32)
            case "generate_random_chars_64":
                # Generate 64 random alphanumeric chars
                return generate_random_chars(64)
            case _:
                raise ValidationError(f"Unsupported template function {template_func}")

    @classmethod
    def process_compose_spec(
        cls,
        user_content: str,
        stack: "ComposeStack",
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
        env_overrides = stack.env_overrides.all()
        override_dict = {env.key: str(env.value) for env in env_overrides}

        # generate temlate values
        for key, env in spec.envs.items():
            template_func = cls._extract_template_expression(env.value)

            if key in override_dict:
                env.value = override_dict[key]  # replace values with existing overrides
            elif template_func is not None:
                env.value = replace_placeholders(
                    env.value,
                    {template_func: cls._generate_template_value(template_func)},
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

            if "default" not in service.networks:
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
        for config_name, config in spec.configs.items():
            if not config.external:
                config.labels.update(
                    {
                        "zane-managed": "true",
                        "zane-stack": stack.id,
                        "zane-project": stack.project_id,
                    }
                )

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
                    for k, v in envs.items():
                        envs[k] = quoted(v)  # always quote env variables

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
            environ=spec.to_dict()["x-env"],
        )

        print("=== BEFORE ===")
        print(before)
        print("=== END BEFORE ===")

        print("=== EXPANDED ===")
        print(expanded)
        print("=== END EXPANDED ===")

        return expanded

    @classmethod
    def extract_new_env_overrides(
        cls,
        spec: ComposeStackSpec,
    ) -> List[Dict[str, Any]]:
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
    def extract_config_contents(cls, spec: ComposeStackSpec) -> Dict[str, str]:
        configs = {
            name: expand(config.content, environ=spec.to_dict()["x-env"])
            for name, config in spec.configs.items()
            if config.is_derived_from_content and config.content is not None
        }
        return configs

    @classmethod
    def extract_service_urls(
        cls,
        spec: ComposeStackSpec,
        stack_hash_prefix: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract URL routing configuration from service labels.

        Parses labels like:
        - zane.http.port: "80"
        - zane.http.routes.0.domain: "example.com"
        - zane.http.routes.0.base_path: "/"
        - zane.http.routes.0.strip_prefix: "false"

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
        service_urls = {}
        environ = spec.to_dict()["x-env"]

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
                    labels.get(f"zane.http.routes.{route_index}.port", "None"),
                    environ=environ,
                )

                domain = str(labels.get(f"zane.http.routes.{route_index}.domain"))
                base_path = str(
                    labels.get(f"zane.http.routes.{route_index}.base_path", "/").strip()
                )
                strip_prefix = str(
                    labels.get(f"zane.http.routes.{route_index}.strip_prefix", "true")
                ).lower()

                route = {
                    "domain": expand(domain, environ=environ),
                    "base_path": expand(base_path, environ=environ),
                    "strip_prefix": expand(strip_prefix, environ=environ) == "true",
                    "port": http_port,
                }
                name = service_name.removeprefix(f"{stack_hash_prefix}_")
                route_dict[f"{name}.deploy.labels.{label}"] = route

                routes.append(route)

            form = ComposeStackURLRouteLabelsSerializer(data={"services": route_dict})
            form.is_valid(raise_exception=True)

            if routes:
                service_urls[service_name.removeprefix(f"{stack_hash_prefix}_")] = (
                    routes
                )

        return service_urls
