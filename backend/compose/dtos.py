from dataclasses import dataclass, field

from typing import Dict, Optional, List, Any


@dataclass
class ComposeEnvVarSpec:
    key: str
    value: str

    def to_dict(self) -> Dict[str, Any]:
        return {self.key: self.value}


@dataclass
class ComposeVolumeSpec:
    """Volume in compose file"""

    name: str
    driver: str = "local"
    driver_opts: Dict[str, str] = field(default_factory=dict)
    external: bool = False
    labels: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComposeVolumeSpec":
        return cls(
            name=data["name"],
            driver=data.get("driver", "local"),
            driver_opts=data.get("driver_opts", {}),
            external=data.get("external", False),
            labels=data.get("labels", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "driver": self.driver,
            "driver_opts": self.driver_opts,
            "external": self.external,
            "labels": self.labels,
        }


@dataclass
class ComposeServiceSpec:
    """
    Service in compose file
    We only included values that we want to override,
    the rest will be reconcilied from the original compose content
    """

    name: str
    image: str
    environment: List[ComposeEnvVarSpec] = field(default_factory=list)
    networks: List[Dict[str, Any]] = field(default_factory=list)
    deploy: Dict[str, Any] = field(default_factory=dict)
    logging: Optional[Dict[str, Any]] = None
    labels: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComposeServiceSpec":
        envs: list[ComposeEnvVarSpec] = []
        for env in data.get("environment", []):
            key, value = env.split("=")
            envs.append(ComposeEnvVarSpec(key=key, value=value))
        return cls(
            name=data["name"],
            image=data["image"],
            environment=envs,
            networks=data.get("networks", []),
            deploy=data.get("deploy", {}),
            labels=data.get("labels", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        env_variables = {}
        for env in self.environment:
            env_variables[env.key] = env.value
        return {
            "name": self.name,
            "image": self.image,
            "environment": env_variables,
            "networks": self.networks,
            "deploy": self.deploy,
            "labels": self.labels,
            "logging": self.logging,
        }


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ComposeStackSpec":
        volumes: Dict[str, ComposeVolumeSpec] = {}
        for name, volume in data.get("volumes", {}).items():
            if isinstance(volume, dict):
                volumes[name] = ComposeVolumeSpec.from_dict({**volume, "name": name})
            else:
                volumes[name] = ComposeVolumeSpec.from_dict({"name": name})

        return cls(
            services={
                name: ComposeServiceSpec.from_dict({**service, "name": name})
                for name, service in data.get("services", {}).items()
            },
            volumes=volumes,
            networks=data.get("networks", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "services": {
                name: {k: v for k, v in service.to_dict().items() if k != "name"}
                for name, service in self.services.items()
            },
            "volumes": {
                name: {k: v for k, v in volume.to_dict().items() if k != "name"}
                for name, volume in self.volumes.items()
            },
            "networks": self.networks,
        }
