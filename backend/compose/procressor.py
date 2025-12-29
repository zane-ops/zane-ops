from yaml import SafeDumper
import yaml
from typing import Dict, Any
from django.core.exceptions import ValidationError
from .dtos import ComposeStackSpec, ComposeEnvVarSpec
from temporal.helpers import get_env_network_resource_name
import json
from django.conf import settings
from zane_api.models import Environment
from .models import ComposeStack


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

    @classmethod
    def _parse_user_yaml(cls, content: str) -> Dict[str, Any]:
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
    def process_compose_spec(
        cls,
        user_content: str,
        stack: "ComposeStack",
        # env_overrides: Dict[
        #     str, Dict[str, str]
        # ],  # Changed: keyed by service_name -> {key: value}
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

        Args:
            user_content: Raw YAML compose file from user
            stack_id: ComposeStack ID (e.g., "srv_cmp_abc123")
            env_id: Environment ID
            project_id: Project ID
            env_overrides: Environment variable overrides grouped by service
                          Format: {"db": {"POSTGRES_USER": "value"}, "web": {...}}
                          Service name can be None for stack-level overrides

        Returns:
            ComposeStackSpec dataclass

        Raises:
            ValidationError: If compose file is invalid
        """
        # Parse YAML
        spec_dict = ComposeSpecProcessor._parse_user_yaml(user_content)

        # Convert to dataclass
        spec = ComposeStackSpec.from_dict(spec_dict)

        # Get environment network name
        env_network_name = get_env_network_resource_name(
            stack.environment_id, stack.project_id
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

        stack_hash = stack.id.replace(ComposeStack.ID_PREFIX, "").lower()

        # Rename services to prevent DNS name collisions in the shared `zane` network
        # Since all stacks share the `zane` network, service names like `app` would collide
        # We prefix them with stack hash to ensure unique DNS names (e.g., abc123_app)
        renamed_services = {}
        for original_name, service in spec.services.items():
            hashed_name = f"{stack_hash}_{original_name}"
            service.name = hashed_name
            renamed_services[hashed_name] = service
        spec.services = renamed_services

        # Rename volumes to prevent collisions
        # renamed_volumes = {}
        # for original_name, volume in spec.volumes.items():
        #     hashed_name = f"{stack_hash}_{original_name}"
        #     volume.name = hashed_name
        #     renamed_volumes[hashed_name] = volume
        # spec.volumes = renamed_volumes

        # Process each service
        for service_name, service in spec.services.items():
            # 1. Add zane & env networks with aliases
            if "zane" not in service.networks:
                service.networks["zane"] = None
            if env_network_name not in service.networks:
                # Add environment network with stable alias for cross-env communication
                # Original service name without stack hash, prefixed with alias_prefix
                original_service_name = service_name.removeprefix(f"{stack_hash}_")
                service.networks[env_network_name] = {
                    "aliases": [f"{stack.alias_prefix}_{original_service_name}"]
                }

            # 2. Add ZaneOps tracking labels
            service.labels.update(
                {
                    "zane-managed": "true",
                    "zane-project": stack.project_id,
                    "zane-environment": stack.environment_id,
                }
            )

            # 3. Add logging configuration (for Fluentd log collection)
            service.logging = {
                "driver": "fluentd",
                "options": {
                    "fluentd-address": settings.ZANE_FLUENTD_HOST,
                    "tag": json.dumps(
                        {
                            "zane.stack": stack.name,
                            "zane.service": service_name.removeprefix(f"{stack_hash}_"),
                        }
                    ),
                    "fluentd-async": "true",  # Non-blocking logging
                    "mode": "non-blocking",
                    "fluentd-max-retries": "10",
                    "fluentd-sub-second-precision": "true",
                },
            }

            # 4. Inject safe update_config for rolling updates
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

            # 6. inject default zane variables
            service.environment["ZANE"] = ComposeEnvVarSpec(key="ZANE", value="true")

        # # Add labels to volumes for tracking
        # if spec.volumes:
        #     for volume_name, volume_spec in spec.volumes.items():
        #         volume_spec.labels.update(
        #             {
        #                 "zane-managed": "true",
        #                 "zane-stack": stack_id,
        #                 "zane-project": project_id,
        #                 "zane-volume": volume_name,
        #             }
        #         )

        return spec

    @classmethod
    def generate_deployable_yaml_dict(
        cls,
        spec: ComposeStackSpec,
        user_content: str,
        stack_id: str,
    ) -> dict:
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

        stack_hash = stack_id.replace(ComposeStack.ID_PREFIX, "").lower()

        # Parse YAML
        user_spec_dict: Dict[str, Dict[str, Any]] = (
            ComposeSpecProcessor._parse_user_yaml(user_content)
        )

        compose_dict: Dict[str, Dict[str, Any]] = spec.to_dict()

        # Reconcile services with hashed names
        # The compose_dict has hashed service names (e.g., "abc123_app")
        # The user_spec_dict has original names (e.g., "app")
        # We need to map original names to hashed names during reconciliation
        reconciled_services = {}
        for original_name, user_service in user_spec_dict.get("services", {}).items():
            hashed_name = f"{stack_hash}_{original_name}"
            computed_service = compose_dict["services"].get(hashed_name, {})

            # Copy over user-specified fields that we didn't process
            for key, value in user_service.items():
                if computed_service.get(key) is None:
                    computed_service[key] = value

            reconciled_services[hashed_name] = computed_service

        compose_dict["services"] = reconciled_services

        # # Reconcile volumes with hashed names
        # reconciled_volumes = {}
        # for original_name, user_volume in user_spec_dict.get("volumes", {}).items():
        #     hashed_name = f"{stack_hash}_{original_name}"
        #     computed_volume = compose_dict.get("volumes", {}).get(hashed_name, {})

        #     # Copy over user-specified fields
        #     if isinstance(user_volume, dict):
        #         for key, value in user_volume.items():
        #             if computed_volume.get(key) is None:
        #                 computed_volume[key] = value

        #     reconciled_volumes[hashed_name] = computed_volume

        # if reconciled_volumes:
        #     compose_dict["volumes"] = reconciled_volumes

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
        stack_id: str,
    ) -> str:
        """
        Convert ComposeStackSpec back to YAML for docker stack deploy,
        and also reconciliate with existing services.

        Args:
            spec: ComposeStackSpec dataclass
            user_content: Original YAML from user
            stack_hash: Stack hash for namespacing (e.g., "abc123")

        Returns:
            YAML string ready for deployment
        """

        # Generate YAML with nice formatting
        return yaml.safe_dump(
            ComposeSpecProcessor.generate_deployable_yaml_dict(
                spec,
                user_content,
                stack_id,
            ),
            default_flow_style=False,
            sort_keys=False,  # Preserve order
            allow_unicode=True,
        )
