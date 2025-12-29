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
        stack_id: str,
        stack_name: str,
        env_id: str,
        project_id: str,
        # env_overrides: Dict[
        #     str, Dict[str, str]
        # ],  # Changed: keyed by service_name -> {key: value}
    ) -> str:
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
        env_network_name = get_env_network_resource_name(env_id, project_id)

        # Inject zane network & environment network to networks section
        if env_network_name not in spec.networks:
            spec.networks[env_network_name] = {
                "external": True,
            }

        if "zane" not in spec.networks:
            spec.networks["zane"] = {
                "external": True,
            }

        # Process each service
        for service_name, service in spec.services.items():
            stack_hash = stack_id.replace(ComposeStack.ID_PREFIX, "")
            env_hash = env_id.replace(Environment.ID_PREFIX, "")
            env_network_aliases = [
                f"zn-{service.name}-{stack_hash}.zaneops.internal",
                f"zn-{service.name}-{stack_hash}",
            ]
            global_network_aliases = [
                f"zn-{service.name}-{stack_hash}.{env_hash}.zaneops.internal",
                f"zn-{service.name}-{stack_hash}.{env_hash}",
            ]

            # 1. Add zane network
            if isinstance(service.networks, list):
                if "zane" not in service.networks:
                    service.networks.append(
                        {"zane": {"aliases": global_network_aliases}}
                    )
                if env_network_name not in service.networks:
                    service.networks.append(
                        {env_network_name: {"aliases": env_network_aliases}}
                    )
            elif isinstance(service.networks, dict):
                if "zane" not in service.networks:
                    service.networks["zane"] = {"aliases": global_network_aliases}
                if env_network_name not in service.networks:
                    service.networks[env_network_name] = {
                        "aliases": env_network_aliases
                    }

            # 2. Add ZaneOps tracking labels
            service.labels.update(
                {
                    "zane-managed": "true",
                    "zane-project": project_id,
                    "zane-environment": env_id,
                }
            )

            # 3. Add logging configuration (for Fluentd log collection)
            service.logging = {
                "driver": "fluentd",
                "options": {
                    "fluentd-address": settings.ZANE_FLUENTD_HOST,
                    "tag": json.dumps(
                        {"zane.stack": stack_name, "zane.service": service_name}
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

            # 5. Set restart policy to "any" (unless user explicitly specified one)
            service.deploy["restart_policy"] = service.deploy.get(
                "restart_policy", "any"
            )

            # 6. inject default zane variables
            service.environment.append(ComposeEnvVarSpec(key="ZANE", value="true"))

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

        return ComposeSpecProcessor._generate_deployable_yaml(spec, spec_dict)

    @classmethod
    def _generate_deployable_yaml(
        cls,
        spec: ComposeStackSpec,
        user_content: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Convert ComposeStackSpec back to YAML for docker stack deploy,
        and also reconciliate with existing services.

        Args:
            spec: ComposeStackSpec dataclass

        Returns:
            YAML string ready for deployment
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
            lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
        )

        # Parse YAML
        compose_dict: Dict[str, Dict[str, Any]] = spec.to_dict()

        for name, user_service in user_content["services"].items():
            computed_service = compose_dict["services"][name]
            for key, value in user_service.items():
                if computed_service.get(key) is None:
                    computed_service[key] = value

        # include other keys that the user modified that we haven't processed yet
        for key, value in user_content.items():
            if compose_dict.get(key) is None:
                compose_dict[key] = value

        # remove empty keys
        compose_dict = {k: v for k, v in compose_dict.items() if v != {} and v != []}

        # Generate YAML with nice formatting
        return yaml.safe_dump(
            compose_dict,
            default_flow_style=False,
            sort_keys=False,  # Preserve order
            allow_unicode=True,
        )
