import base64
import json
import os
import re
import tomllib
import yaml
from typing import Dict, Any


from zane_api.utils import jprint
from .dtos import DokployConfigMount, DokployConfigObject, ComposeServiceSpec
from abc import ABC, abstractmethod
import tempfile


class BaseComposeAdapter(ABC):
    @classmethod
    @abstractmethod
    def to_zaneops(cls, template: str) -> str: ...


class DokployComposeAdapter(BaseComposeAdapter):
    """
    Adapter to support templates from dokploy
    """

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
        """
        Transform a dokploy template to ZaneOps compatible stack.

        * Add all the config.mounts as docker configs
        * replace all the variable placeholders to ZaneOps compatible expressions (ex: ${password} to {{ generate_password | 32 }})
        * replace all the dokploy relative bind mounts (`..files/`) to configs or volumes whenever possible
        * Remove the exposed ports that are supposed to be domains, as well as remove `expose:` as it is useless
        - Make sure `depends_on` is a list
        """

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

        # handle variables first
        x_env: dict[str, str] = {}
        for key, value in config.variables.items():
            # Convert Dokploy placeholders to ZaneOps template expressions
            converted_value = cls._convert_dokploy_placeholder_to_zaneops(value)
            x_env[key] = converted_value

        # Process config.env
        for key, value in config.env.items():
            # Check if this is a self-reference to a definition in
            # like this:

            # [variables]
            # KENER_SECRET_KEY = "${password:64}" -> replaced with "{{ generate_password | 64 }}"
            #
            # [[config.env]]
            # KENER_SECRET_KEY = "KENER_SECRET_KEY"

            # expected result:
            #   -> { "KENER_SECRET_KEY": "{{ generate_password | 64 }}" }

            if value == f"${{{key}}}" and key in x_env:
                # Self-reference: skip it, keep the variable definition
                continue
            else:
                # Not a self-reference: override the variable
                # [variables]
                # DB_PASSWORD = "${password:32}" -> replaced with "{{ generate_password | 32 }}"
                #
                # [[config.env]]
                # MYSQL_PASSWORD = "password"
                # DB_PASSWORD = "whatever"

                # expected result:
                #   -> { "MYSQL_PASSWORD": "password", "DB_PASSWORD": "whatever" }
                converted_value = cls._convert_dokploy_placeholder_to_zaneops(value)
                x_env[key] = converted_value

        if x_env:
            compose_dict["x-zane-env"] = x_env

        # handle domains
        for service_name, domains in config.domains.items():
            compose_service = compose_dict["services"].get(service_name)
            service = ComposeServiceSpec.from_dict(
                {**compose_service, "name": service_name}
            )

            if compose_service is not None:
                deploy = compose_service.get("deploy", {})
                deploy["labels"] = deploy.get("labels", {})

                for index, domain in enumerate(domains):
                    deploy["labels"][f"zane.http.routes.{index}.domain"] = domain.host
                    deploy["labels"][f"zane.http.routes.{index}.base_path"] = (
                        domain.path
                    )
                    deploy["labels"][f"zane.http.routes.{index}.port"] = domain.port
                    deploy["labels"][f"zane.http.routes.{index}.strip_prefix"] = "false"

                compose_service["deploy"] = deploy
                # remove ports section for services
                compose_service.pop("ports", None)
                # Remove `expose` property as it is useless
                compose_service.pop("expose", None)
                # Remove `restart` property as it is also ignored
                compose_service.pop("restart", None)

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            """
            # we need reconcile these cases:

           ** 1st case: 
            mounts:
                - "./clickhouse_config/logging_rules.xml"
                - "./clickhouse_config/network.xml"
                - "./clickhouse_config/user_logging.xml"

            volumes:
                - ../files/clickhouse_config:/etc/clickhouse-server/config.d

            === Expected result ===
            configs:
                - source: logging_rules.xml
                  target: /etc/clickhouse-server/config.d/logging_rules.xml
                - source: network.xml
                  target: /etc/clickhouse-server/config.d/network.xml
                - source: user_logging.xml
                  target: /etc/clickhouse-server/config.d/user_logging.xml

            ** 2nd case: 
            mounts:
                - "clickhouse/clickhouse-config.xml"
                - "clickhouse/clickhouse-user-config.xml"
                - "clickhouse/init-db.sql"

            volumes:
                - ../files/clickhouse/clickhouse-config.xml:/etc/clickhouse-server/config.d/op-config.xml:ro
                - ../files/clickhouse/clickhouse-user-config.xml:/etc/clickhouse-server/users.d/op-user-config.xml:ro
                - ../files/clickhouse/init-db.sql:/docker-entrypoint-initdb.d/1_init-db.sql:ro

            === Expected result ===
            configs:
                - source: clickhouse-config.xml
                  target: /etc/clickhouse-server/config.d/op-config.xml
                - source: clickhouse-user-config.xml
                  target: /etc/clickhouse-server/users.d/op-user-config.xml
                - source: init-db.sql
                  target: /docker-entrypoint-initdb.d/1_init-db.sql

            === Solution ===
            1. create a temp dir
            2. for each mount path, create a file at the selected path inside the temp dir, also create a config with the content
            2.5. Do we also need to create a folder for bind mounts ? -> maybe not
            3. find the path of the volume:
                - if the volume path is a dir, we need to find all the files in that directory
                    and create a config mapping from the filename (which is a config) to the volume target
                - if the volume path is a file:
                    replace with a config mapping directly

                - if the volume path doesn't exist (?) and is relative path:
                    replace with new volume (and create it in compose)

            """

            # Step 1: Create temp dir (already done by context manager)
            # Step 2: For each mount path, create a file at the selected path inside the temp dir
            mount_path_to_config: dict[str, DokployConfigMount] = {}
            for mount in config.mounts:
                # Create file in temp directory
                file_path = os.path.join(tmpdir, mount.filePath)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                with open(file_path, "w") as f:
                    f.write(mount.content)

                # Track which mount paths exist
                relative_path = os.path.relpath(file_path, tmpdir)
                mount_path_to_config[relative_path] = mount

            # create configs
            configs: dict[str, dict] = {}
            for mount in config.mounts:
                filename = os.path.basename(mount.filePath)
                configs[filename] = dict(content=mount.content)

            # Step 3: Find the path of the volume and handle it
            for service_name, service_dict in compose_dict["services"].items():
                service = ComposeServiceSpec.from_dict(
                    {**service_dict, "name": service_name}
                )

                ## Handle volumes and config mounts
                volumes_to_keep = []
                service_configs = service_dict.get("configs", [])

                for volume in service.volumes:
                    if (
                        volume.type == "bind"
                        and volume.source is not None
                        # ../files prefix are relative dokploy files, all of them should be replaced with configs/volumes
                        and volume.source.startswith("../files")
                    ):
                        # Remove the ../files prefix
                        _, relative_path = volume.source.split("../files/", 1)
                        full_path = os.path.join(tmpdir, relative_path)

                        print(f"{relative_path=}")
                        print(f"{full_path=}")

                        # Check if the volume path is a dir or file
                        if os.path.isdir(full_path):
                            print(f"os.path.isdir({full_path=})")
                            # Case 1: Directory - find all files in that directory
                            for root, dirs, files in os.walk(full_path):
                                for file in files:
                                    file_full_path = os.path.join(root, file)
                                    # Get relative path from tmpdir
                                    # so that `file_rel_path` which would be `/var/tmp/folder/file.txt` becomes `folder/file.txt`
                                    file_rel_path = os.path.relpath(
                                        file_full_path, tmpdir
                                    )

                                    # Find the matching mount
                                    matching_mount = mount_path_to_config.get(
                                        file_rel_path
                                    )
                                    if matching_mount:
                                        config_name = os.path.basename(
                                            matching_mount.filePath
                                        )
                                        # Target is volume target + filename
                                        config_target = os.path.join(
                                            volume.target, file
                                        )

                                        service_configs.append(
                                            {
                                                "source": config_name,
                                                "target": config_target,
                                            }
                                        )
                        elif os.path.isfile(full_path):
                            print(f"os.path.isfile({full_path=})")
                            # Case 2: File - replace with config mapping directly
                            file_rel_path = os.path.relpath(full_path, tmpdir)

                            # Find the matching mount
                            matching_mount = mount_path_to_config.get(file_rel_path)

                            if matching_mount:
                                config_name = os.path.basename(matching_mount.filePath)
                                service_configs.append(
                                    {
                                        "source": config_name,
                                        "target": volume.target,
                                    }
                                )
                        else:
                            # Case 3: Path doesn't exist and is relative - create new volume
                            # Extract volume name from relative path
                            volume_name = relative_path.replace("/", "_").replace(
                                ".", "_"
                            )
                            if volume_name not in compose_dict.get("volumes", {}):
                                if "volumes" not in compose_dict:
                                    compose_dict["volumes"] = {}
                                compose_dict["volumes"][volume_name] = {}

                            # transform into a volume mount
                            volume.type = "volume"
                            volume.source = volume_name
                            volumes_to_keep.append(volume.to_dict())
                    else:
                        # Not a ../files bind mount, keep it
                        volumes_to_keep.append(volume.to_dict())

                service_dict["volumes"] = volumes_to_keep
                if service_configs:
                    service_dict["configs"] = service_configs

                ## handle depends_on
                if service.depends_on:
                    service_dict["depends_on"] = service.depends_on

            if configs:
                compose_dict["configs"] = configs

        # we need to reorder the compose file properties
        compose = {}
        if compose_dict.get("version"):
            compose["version"] = compose_dict.pop("version")
        if compose_dict.get("x-zane-env"):
            compose["x-zane-env"] = compose_dict.pop("x-zane-env")
        compose["services"] = compose_dict.pop("services")
        compose.update(compose_dict)

        print("=== translated compose ===")
        jprint(compose)

        return yaml.safe_dump(compose, sort_keys=False)
