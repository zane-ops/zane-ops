import base64
import json
import re
import tomllib
import yaml
from typing import Dict, Any


from zane_api.utils import jprint
from .dtos import DokployConfigObject
from abc import ABC, abstractmethod


class BaseComposeAdapter(ABC):
    @classmethod
    @abstractmethod
    def to_zaneops(cls, template: str) -> str: ...


class DokployComposeAdapter(BaseComposeAdapter):
    # Dokploy placeholder pattern for password-like values (password, base64, hash, jwt)
    # These all map to generate_password in ZaneOps
    DOKPLOY_PASSWORD_LIKE_PATTERN = re.compile(
        r"^\$\{(?:password|base64|hash|jwt)(?::(\d+))?\}$"
    )

    # Direct Mapping from Dokploy placeholders to ZaneOps template expressions
    PLACEHOLDER_MAPPING = {
        "${domain}": "{{ generate_domain }}",
        "${email}": "{{ generate_email }}",
        "${username}": "{{ generate_username }}",
        "${uuid}": "{{ generate_uuid }}",
    }

    @classmethod
    def _convert_dokploy_placeholder_to_zaneops(cls, value: str) -> str:
        """
        Convert a Dokploy placeholder to a ZaneOps template expression.

        Args:
            value: The Dokploy placeholder (e.g., "${domain}", "${password:32}")

        Returns:
            The equivalent ZaneOps template expression (e.g., "{{ generate_domain }}", "{{ generate_password | 32 }}")
            or the original value if no conversion is needed
        """
        # Check simple mappings first
        if value in cls.PLACEHOLDER_MAPPING:
            return cls.PLACEHOLDER_MAPPING[value]

        # Check password-like patterns (password, base64, hash, jwt) with optional length
        password_like_match = cls.DOKPLOY_PASSWORD_LIKE_PATTERN.match(value)
        if password_like_match:
            length = password_like_match.group(1)
            if length:
                return f"{{{{ generate_password | {length} }}}}"
            else:
                # Default length is 32
                return "{{ generate_password | 32 }}"

        # If no pattern matches, return the value as-is
        return value

    @classmethod
    def to_zaneops(cls, template: str):
        decoded_data = base64.b64decode(template)
        decoded_string = decoded_data.decode("utf-8")
        template_dict = json.loads(decoded_string)

        compose_dict: Dict[str, Any] = yaml.safe_load(template_dict["compose"])
        config_dict: Dict[str, Any] = tomllib.loads(template_dict["config"])

        print("=== compose ===")
        jprint(compose_dict)
        print("=== config ===")
        jprint(config_dict)

        config = DokployConfigObject.from_dict(config_dict)

        print(config)

        # handle variables first
        x_env: dict[str, str] = {}
        for key, value in config.variables.items():
            # Convert Dokploy placeholders to ZaneOps template expressions
            converted_value = cls._convert_dokploy_placeholder_to_zaneops(value)
            x_env[key] = converted_value

        x_env.update(config.env)
        if x_env:
            compose_dict["x-env"] = x_env

        for service_name, domains in config.domains.items():
            compose_service = compose_dict["services"].get(service_name)
            if compose_service is not None:
                deploy = compose_service.get("deploy", {})
                deploy["labels"] = deploy.get("labels", {})

                for index, domain in enumerate(domains):
                    deploy["labels"][f"zane.http.routes.{index}.domain"] = domain.host
                    deploy["labels"][f"zane.http.routes.{index}.base_path"] = (
                        domain.path
                    )
                    deploy["labels"][f"zane.http.routes.{index}.port"] = domain.port
                compose_service["deploy"] = deploy

        # we need to reorder the compose file properties
        compose = {}
        if compose_dict.get("version"):
            compose["version"] = compose_dict.pop("version")
        if compose_dict.get("x-env"):
            compose["x-env"] = compose_dict.pop("x-env")
        compose["services"] = compose_dict.pop("services")
        compose.update(compose_dict)

        return yaml.safe_dump(compose, sort_keys=False)
