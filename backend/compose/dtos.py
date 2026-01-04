from dataclasses import dataclass, field
from typing import Dict, Literal, Optional, List, Any, Self, cast
from enum import Enum


class ComposeStackServiceStatus(Enum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    UNHEALTHY = "UNHEALTHY"
    COMPLETE = "COMPLETE"


@dataclass
class ComposeEnvVarSpec:
    key: str
    value: str

    is_newly_generated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {self.key: self.value}


@dataclass
class ComposeVolumeMountSpec:
    target: str
    source: Optional[str] = None
    type: Literal["volume", "bind", "tmpfs"] = "volume"
    read_only: bool = False
    bind: Optional[Dict] = None
    image: Optional[Dict] = None
    consistency: Optional[Dict] = None
    tmpfs: Optional[Dict] = None
    volume: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        spec_dict: Dict[str, Any] = {
            "type": self.type,
            "target": self.target,
        }

        if self.source is not None:
            spec_dict.update(source=self.source)

        if self.read_only:
            spec_dict.update(read_only=True)

        if self.bind is not None:
            spec_dict.update(bind=self.bind)

        if self.image is not None:
            spec_dict.update(image=self.image)

        if self.consistency is not None:
            spec_dict.update(consistency=self.consistency)

        if self.tmpfs is not None:
            spec_dict.update(tmpfs=self.tmpfs)

        if self.volume is not None:
            spec_dict.update(volume=self.volume)

        return spec_dict


@dataclass
class ComposeServiceSpec:
    """
    Service in compose file
    We only included values that we want to override,
    the rest will be reconcilied from the original compose content
    """

    name: str
    image: str
    environment: Dict[str, ComposeEnvVarSpec] = field(default_factory=dict)
    networks: Dict[str, Dict[str, Any] | None] = field(default_factory=dict)
    deploy: Dict[str, Any] = field(default_factory=dict)
    logging: Optional[Dict[str, Any]] = None
    volumes: list[ComposeVolumeMountSpec] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComposeServiceSpec":
        # handle envs
        envs: Dict[str, ComposeEnvVarSpec] = {}
        original_env = data.get("environment", [])
        if isinstance(original_env, list):
            for env in original_env:
                key, value = env.split("=")
                envs[key] = ComposeEnvVarSpec(key=key, value=value)
        elif isinstance(original_env, dict):
            for key, value in original_env.items():
                envs[key] = ComposeEnvVarSpec(key=key, value=value)

        # handle networks - convert to dict format
        networks: Dict[str, Any] = {}
        original_networks = data.get("networks", [])
        if isinstance(original_networks, list):
            # List format: ["zane", "custom_network"]
            for network_name in original_networks:
                networks[network_name] = None
        elif isinstance(original_networks, dict):
            # Dict format: {"zane": {aliases: [...]}, "custom": null}
            networks = original_networks

        volumes: List[ComposeVolumeMountSpec] = []
        original_volumes = data.get("volumes", [])

        # handle volumes convert to dict format
        for v in original_volumes:
            image = None
            consistency = None
            tmpfs = None
            volume = None
            bind = None
            if isinstance(v, str):
                # str format: "db-data:/var/lib/postgresql:rw"
                parts = v.split(":")
                source = parts[0]
                target = parts[1]
                volume_type = (
                    "bind"
                    if source.startswith("/")
                    or source.startswith("./")
                    or source.startswith("../")
                    else "volume"
                )
                read_only = False
                if len(parts) > 2:
                    mode = parts[2]
                    if mode == "ro":
                        read_only = True
                    if mode in ["z", "Z"]:
                        # selinux mode
                        # see: https://docs.docker.com/reference/compose-file/services/#short-syntax-5
                        bind = {"selinux": mode}
            else:
                # Dict format: {"type": "bind", "source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}
                v = cast(dict, v)
                volume_type = v.get("type", "volume")
                target = v["target"]
                source = v.get("source")
                read_only = v.get("read_only", False)
                bind = v.get("bind")

                image = v.get("image")
                consistency = v.get("consistency")
                tmpfs = v.get("tmpfs")
                volume = v.get("volume")

            volumes.append(
                ComposeVolumeMountSpec(
                    source=source,
                    target=target,
                    type=volume_type,
                    read_only=read_only,
                    bind=bind,
                    image=image,
                    consistency=consistency,
                    tmpfs=tmpfs,
                    volume=volume,
                )
            )

        return cls(
            name=data["name"],
            image=data["image"],
            environment=envs,
            networks=networks,
            volumes=volumes,
            deploy=data.get("deploy", {}),
            depends_on=data.get("depends_on", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        # Convert environment from Dict[str, ComposeEnvVarSpec] to Dict[str, str]
        spec_dict = {
            "image": self.image,
            "networks": self.networks,
            "deploy": self.deploy,
            "logging": self.logging,
        }

        if len(self.volumes) > 0:
            spec_dict.update(volumes=[volume.to_dict() for volume in self.volumes])

        if len(self.depends_on) > 0:
            spec_dict.update(depends_on=self.depends_on)

        env_dict = {}
        for env_spec in self.environment.values():
            env_dict.update(env_spec.to_dict())

        if env_dict:
            spec_dict.update(environment=env_dict)

        return spec_dict


@dataclass
class ComposeVolumeSpec:
    """Volume in compose file"""

    name: str
    driver: str = "local"
    external: bool = False
    driver_opts: Optional[Dict] = None
    labels: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComposeVolumeSpec":
        return cls(
            name=data["name"],
            driver=data.get("driver", "local"),
            driver_opts=data.get("driver_opts", None),
            external=data.get("external", False),
            labels=data.get("labels", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        spec_dict: Dict[str, Any] = {
            "driver": self.driver,
        }
        if self.labels:
            spec_dict.update(labels=self.labels)
        if self.external:
            spec_dict.update(external=True)
            spec_dict.pop("driver")
        if self.driver_opts is not None:
            spec_dict.update(driver_opts=self.driver_opts)

        return spec_dict


@dataclass
class ComposeConfigSpec:
    file: Optional[str] = None
    content: Optional[str] = None
    name: Optional[str] = None
    external: bool = False
    labels: Dict[str, str] = field(default_factory=dict)

    # technically there is an `environment: Optional[str]` field, but it's ignored since it's not
    # supported by docker stack yet
    # `content` is also not supported, but ZaneOps handles them by transforming them into `file` references

    is_derived_from_content: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        return cls(
            file=data.get("file"),
            content=data.get("content"),
            name=data.get("name"),
            external=data.get("external", False),
            labels=data.get("labels", {}),
        )

    def to_dict(self):
        spec_dict: Dict[str, Any] = {}

        if self.file:
            spec_dict.update(file=self.file)

        if self.content and not self.is_derived_from_content:
            spec_dict.update(content=self.content)

        if self.external:
            spec_dict.update(external=True)

        if self.name:
            spec_dict.update(name=self.name)
        if self.labels:
            spec_dict.update(labels=self.labels)

        return spec_dict


@dataclass
class ComposeStackSpec:
    """
    Simple compose specification
    We only included values that we want to override,
    the rest will be reconcilied from the original compose content
    """

    services: Dict[str, ComposeServiceSpec] = field(default_factory=dict)
    volumes: Dict[str, ComposeVolumeSpec] = field(default_factory=dict)
    networks: Dict[str, Any] = field(default_factory=dict)
    configs: Dict[str, ComposeConfigSpec] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComposeStackSpec":
        volumes: Dict[str, ComposeVolumeSpec] = {}
        for name, volume in data.get("volumes", {}).items():
            # dict format: { "db-data": {driver: "local"}, ...}
            if isinstance(volume, dict):
                volumes[name] = ComposeVolumeSpec.from_dict({**volume, "name": name})
            else:
                # str format: just the name
                volumes[name] = ComposeVolumeSpec.from_dict({"name": name})

        return cls(
            services={
                name: ComposeServiceSpec.from_dict({**service, "name": name})
                for name, service in data.get("services", {}).items()
            },
            volumes=volumes,
            networks=data.get("networks", {}),
            configs={
                name: ComposeConfigSpec.from_dict(config)
                for name, config in data.get("configs", {}).items()
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "services": {
                name: service.to_dict() for name, service in self.services.items()
            },
            "volumes": {
                name: volume.to_dict() for name, volume in self.volumes.items()
            },
            "networks": self.networks,
            "configs": {
                name: config.to_dict() for name, config in self.configs.items()
            },
        }


@dataclass
class ComposeStackUrlRouteDto:
    domain: str
    base_path: str
    strip_prefix: bool
    port: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        return cls(
            domain=data["domain"],
            base_path=data["base_path"],
            strip_prefix=data["strip_prefix"],
            port=data["port"],
        )

    def to_dict(self):
        return {
            "domain": self.domain,
            "base_path": self.base_path,
            "strip_prefix": self.strip_prefix,
            "port": self.port,
        }


@dataclass
class ComposeStackEnvOverrideDto:
    id: str
    service: str
    key: str
    value: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        return cls(
            id=data["id"],
            service=data["service"],
            key=data["key"],
            value=data["value"],
        )

    def to_dict(self):
        return {
            "id": self.id,
            "service": self.service,
            "key": self.key,
            "value": self.value,
        }


@dataclass
class ComposeStackSnapshot:
    id: str
    slug: str
    network_alias_prefix: str
    user_content: str
    computed_content: str
    urls: Dict[str, List[ComposeStackUrlRouteDto]] = field(default_factory=dict)
    configs: Dict[str, str] = field(default_factory=dict)
    env_overrides: List[ComposeStackEnvOverrideDto] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        urls: Dict[str, List[ComposeStackUrlRouteDto]] = {}
        for service_name, routes in data.get("urls", {}).items():
            urls[service_name] = [
                ComposeStackUrlRouteDto.from_dict(route) for route in routes
            ]

        return cls(
            id=data["id"],
            slug=data["slug"],
            network_alias_prefix=data["network_alias_prefix"],
            user_content=data["user_content"],
            computed_content=data["computed_content"],
            urls=urls,
            configs=data.get("configs", {}),
            env_overrides=[
                ComposeStackEnvOverrideDto.from_dict(env)
                for env in data.get("env_overrides", [])
            ],
        )

    def to_dict(self):
        return {
            "id": self.id,
            "slug": self.slug,
            "network_alias_prefix": self.network_alias_prefix,
            "user_content": self.user_content,
            "computed_content": self.computed_content,
            "urls": {
                service: [route.to_dict() for route in routes]
                for service, routes in self.urls.items()
            },
            "configs": self.configs,
            "env_overrides": [env.to_dict() for env in self.env_overrides],
        }
