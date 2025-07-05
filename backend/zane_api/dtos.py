from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, Mapping


@dataclass
class VolumeDto:
    container_path: str
    mode: Literal["READ_ONLY", "READ_WRITE"]
    name: Optional[str] = None
    host_path: Optional[str] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class ConfigDto:
    mount_path: str
    contents: str
    language: str
    version: Optional[int] = 1
    name: Optional[str] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class URLRedirectToDto:
    url: str
    permanent: bool = False


@dataclass
class URLDto:
    domain: str
    base_path: str
    strip_prefix: bool
    id: Optional[str] = None
    associated_port: Optional[int] = None
    redirect_to: Optional[URLRedirectToDto] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class EnvVariableDto:
    key: str
    value: str
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class PortConfigurationDto:
    forwarded: int
    host: int = 0
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class HealthCheckDto:
    type: Literal["PATH", "COMMAND"]
    value: str
    timeout_seconds: int
    interval_seconds: int
    associated_port: Optional[int] = None
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class DockerCredentialsDto:
    username: str
    password: str

    @classmethod
    def from_dict(cls, data: Dict[str, str]):
        return cls(**data)

    def to_dict(self):
        return dict(username=self.username, password=self.password)


@dataclass
class MemoryLimitDto:
    unit: Literal["BYTES", "KILOBYTES", "MEGABYTES", "GIGABYTES"]
    value: int


@dataclass
class ResourceLimitsDto:
    cpus: Optional[float] = None
    memory: Optional[MemoryLimitDto] = None

    @classmethod
    def from_dict(cls, data: Dict[str, float | dict]):
        memory_dict = data.get("memory")
        memory = MemoryLimitDto(**memory_dict) if memory_dict is not None else None  # type: ignore
        return cls(
            cpus=data.get("cpus"),  # type: ignore
            memory=memory,
        )

    def to_dict(self):
        return dict(
            cpu=self.cpus,
            memory=(
                dict(
                    unit=self.memory.unit,
                    value=self.memory.value,
                )
                if self.memory is not None
                else None
            ),
        )


@dataclass
class EnvironmentVariableDto:
    key: str
    value: str
    id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)


@dataclass
class EnvironmentDto:
    id: str
    is_preview: bool
    name: str
    variables: List[EnvironmentVariableDto] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, str | bool]):
        return cls(**data)  # type: ignore

    def to_dict(self):
        return dict(id=self.id, is_preview=self.is_preview, name=self.name)


@dataclass
class DockerfileBuilderOptions:
    dockerfile_path: str
    build_context_dir: str
    build_stage_target: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, str]):
        return cls(**data)

    def to_dict(self):
        return dict(
            dockerfile_path=self.dockerfile_path,
            build_context_dir=self.build_context_dir,
            build_stage_target=self.build_stage_target,
        )


@dataclass
class StaticDirectoryBuilderOptions:
    publish_directory: str
    index_page: str
    is_spa: bool = False
    not_found_page: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

    def to_dict(self):
        return dict(
            publish_directory=self.publish_directory,
            is_spa=self.is_spa,
            index_page=self.index_page,
            not_found_page=self.not_found_page,
        )


@dataclass
class NixpacksBuilderOptions:
    build_directory: str
    publish_directory: str
    is_static: bool = False
    custom_install_command: Optional[str] = None
    custom_build_command: Optional[str] = None
    custom_start_command: Optional[str] = None

    # static options
    index_page: Optional[str] = None
    is_spa: Optional[bool] = False
    not_found_page: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

    def to_dict(self):
        return dict(
            build_directory=self.build_directory,
            is_static=self.is_static,
            custom_install_command=self.custom_install_command,
            custom_build_command=self.custom_build_command,
            custom_start_command=self.custom_start_command,
            publish_directory=self.publish_directory,
            is_spa=self.is_spa,
            index_page=self.index_page,
            not_found_page=self.not_found_page,
        )


@dataclass
class GitHubAppDto:
    id: str
    name: str
    installation_id: int
    app_url: str
    app_id: int


@dataclass
class GitlabAppDto:
    id: str


@dataclass
class GitAppDto:
    id: str
    github: Optional[GitHubAppDto] = None
    gitlab: Optional[GitlabAppDto] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        github_dict = data.get("github")
        gitlab_dict = data.get("gitlab")

        github = (
            GitHubAppDto(
                id=github_dict["id"],
                name=github_dict["name"],
                installation_id=github_dict["installation_id"],
                app_url=github_dict["app_url"],
                app_id=github_dict["app_id"],
            )
            if github_dict is not None
            else None
        )
        gitlab = GitlabAppDto(**gitlab_dict) if gitlab_dict is not None else None

        return cls(
            id=data["id"],
            github=github,
            gitlab=gitlab,
        )

    def to_dict(self):
        return dict(
            id=self.id,
            github=(
                dict(
                    id=self.github.id,
                    app_url=self.github.app_url,
                    app_id=self.github.app_id,
                    installation_id=self.github.installation_id,
                )
                if self.github is not None
                else None
            ),
            gitlab=(dict(id=self.gitlab.id) if self.gitlab is not None else None),
        )


@dataclass
class DockerServiceSnapshot:
    project_id: str
    id: str
    slug: str
    network_alias: str
    environment: EnvironmentDto
    type: Literal["DOCKER_REGISTRY", "GIT_REPOSITORY"] = "DOCKER_REGISTRY"

    # docker service attributes
    image: Optional[str] = None
    credentials: Optional[DockerCredentialsDto] = None
    command: Optional[str] = None

    # git service attributes
    repository_url: Optional[str] = None
    branch_name: Optional[str] = None
    commit_sha: Optional[str] = None
    builder: Optional[Literal["DOCKERFILE", "STATIC_DIR", "NIXPACKS", "RAILPACK"]] = (
        None
    )
    dockerfile_builder_options: Optional[DockerfileBuilderOptions] = None
    static_dir_builder_options: Optional[StaticDirectoryBuilderOptions] = None
    nixpacks_builder_options: Optional[NixpacksBuilderOptions] = None
    railpack_builder_options: Optional[NixpacksBuilderOptions] = None

    # common attributes
    network_aliases: List[str] = field(default_factory=list)
    healthcheck: Optional[HealthCheckDto] = None
    resource_limits: Optional[ResourceLimitsDto] = None
    volumes: List[VolumeDto] = field(default_factory=list)
    ports: List[PortConfigurationDto] = field(default_factory=list)
    env_variables: List[EnvVariableDto] = field(default_factory=list)
    system_env_variables: List[EnvVariableDto] = field(default_factory=list)
    urls: List[URLDto] = field(default_factory=list)
    configs: List[ConfigDto] = field(default_factory=list)

    # git app
    git_app: Optional[GitAppDto] = None

    @property
    def http_ports(self) -> List[PortConfigurationDto]:
        return [
            port for port in self.ports if port.host is None or port.host in [80, 443]
        ]

    @property
    def urls_with_associated_ports(self) -> List[URLDto]:
        return [url for url in self.urls if url.associated_port is not None]

    @property
    def non_read_only_volumes(self) -> List[VolumeDto]:
        return [volume for volume in self.volumes if volume.mode != "READ_ONLY"]

    @property
    def host_volumes(self) -> List[VolumeDto]:
        return [volume for volume in self.volumes if volume.host_path is not None]

    @property
    def docker_volumes(self) -> List[VolumeDto]:
        return [volume for volume in self.volumes if volume.host_path is None]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DockerServiceSnapshot":
        volumes = [VolumeDto.from_dict(item) for item in data.get("volumes", [])]
        configs = [ConfigDto.from_dict(item) for item in data.get("configs", [])]
        urls = [URLDto.from_dict(item) for item in data.get("urls", [])]
        ports = [PortConfigurationDto.from_dict(item) for item in data.get("ports", [])]
        env_variables = [
            EnvVariableDto.from_dict(item) for item in data.get("env_variables", [])
        ]
        system_env_variables = [
            EnvVariableDto.from_dict(
                {
                    "key": item["key"],
                    "value": item["value"],
                }
            )
            for item in data.get("system_env_variables", [])
        ]
        healthcheck = (
            HealthCheckDto.from_dict(data["healthcheck"])
            if data.get("healthcheck") is not None
            else None
        )
        credentials = (
            DockerCredentialsDto.from_dict(data["credentials"])
            if data.get("credentials") is not None
            else None
        )
        resource_limits = (
            ResourceLimitsDto.from_dict(data["resource_limits"])
            if data.get("resource_limits") is not None
            else None
        )
        git_app = (
            GitAppDto.from_dict(data["git_app"])
            if data.get("git_app") is not None
            else None
        )
        environment = EnvironmentDto.from_dict(data["environment"])

        # dockerfile builder
        dockerfile_builder_options = (
            DockerfileBuilderOptions.from_dict(data["dockerfile_builder_options"])
            if data.get("dockerfile_builder_options") is not None
            else None
        )

        # static dir builder
        static_builder_options = {**(data.get("static_dir_builder_options") or {})}
        static_builder_options.pop("generated_caddyfile", None)
        static_dir_builder_options = (
            StaticDirectoryBuilderOptions.from_dict(static_builder_options)
            if static_builder_options
            else None
        )

        # nixpacks builder
        nixpack_builder_options = {**(data.get("nixpacks_builder_options") or {})}
        nixpack_builder_options.pop("generated_caddyfile", None)
        nixpacks_builder_options = (
            NixpacksBuilderOptions.from_dict(nixpack_builder_options)
            if nixpack_builder_options
            else None
        )

        # railpack builder
        railpacks_builder_options = {**(data.get("railpack_builder_options") or {})}
        railpacks_builder_options.pop("generated_caddyfile", None)
        railpack_builder_options = (
            NixpacksBuilderOptions.from_dict(railpacks_builder_options)
            if railpacks_builder_options
            else None
        )

        return cls(
            image=data.get("image"),
            urls=urls,
            git_app=git_app,
            volumes=volumes,
            type=data.get("type", "DOCKER_REGISTRY"),
            repository_url=data.get("repository_url"),
            branch_name=data.get("branch_name"),
            commit_sha=data.get("commit_sha"),
            builder=data.get("builder"),
            dockerfile_builder_options=dockerfile_builder_options,
            static_dir_builder_options=static_dir_builder_options,
            nixpacks_builder_options=nixpacks_builder_options,
            railpack_builder_options=railpack_builder_options,
            configs=configs,
            command=data.get("command"),
            ports=ports,
            env_variables=env_variables,
            healthcheck=healthcheck,
            system_env_variables=system_env_variables,
            credentials=credentials,
            environment=environment,
            resource_limits=resource_limits,
            id=data["id"],
            project_id=data["project_id"],
            network_aliases=data["network_aliases"],
            slug=data["slug"],
            network_alias=data["network_alias"],
        )

    def has_duplicate_volumes(self) -> bool:
        # Create dictionaries to keep track of seen host_paths and container_paths
        host_path_counts = defaultdict(int)
        container_path_counts = defaultdict(int)

        # Iterate through the volumes and count occurrences of host_path and container_path
        for volume in self.volumes:
            if volume.host_path is not None:
                host_path_counts[volume.host_path] += 1
            if volume.container_path is not None:
                container_path_counts[volume.container_path] += 1

        # Check if any host_path or container_path appears more than once
        has_duplicate_host_path = any(count > 1 for count in host_path_counts.values())
        has_duplicate_container_path = any(
            count > 1 for count in container_path_counts.values()
        )

        # Return True if there are duplicates in either host_path or container_path
        return has_duplicate_host_path or has_duplicate_container_path

    def has_duplicate_configs(self) -> bool:
        # Create dictionaries to keep track of seen host_paths and container_paths
        mount_path_counts = defaultdict(int)

        # Iterate through the volumes and count occurrences of host_path and container_path
        for config in self.configs:
            if config.mount_path is not None:
                mount_path_counts[config.mount_path] += 1

        # Check if any host_path or container_path appears more than once
        has_duplicate_mount_paths = any(
            count > 1 for count in mount_path_counts.values()
        )

        # Return True if there are duplicates in either host_path or container_path
        return has_duplicate_mount_paths

    @property
    def duplicate_envs(self) -> List[str]:
        env_values = defaultdict(int)

        for env in self.env_variables:
            env_values[env.key] += 1

        return [key for key, value in env_values.items() if value > 1]


@dataclass
class DeploymentChangeDto:
    type: Literal["ADD", "UPDATE", "DELETE"]
    field: str
    item_id: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


class RuntimeLogLevel:
    ERROR = "ERROR"
    INFO = "INFO"


class RuntimeLogSource:
    SYSTEM = "SYSTEM"
    PROXY = "PROXY"
    SERVICE = "SERVICE"


@dataclass
class RuntimeLogDto:
    id: str
    created_at: str
    time: str
    level: Literal["ERROR", "INFO"]
    source: Literal["SYSTEM", "PROXY", "SERVICE"]
    service_id: Optional[str] = None
    deployment_id: Optional[str] = None
    content: Optional[str] = None
    content_text: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)
