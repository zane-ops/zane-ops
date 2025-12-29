from dataclasses import dataclass, field

from typing import Dict, Literal, Optional, List, Any


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
    environment: Dict[str, ComposeEnvVarSpec] = field(default_factory=dict)
    networks: Dict[str, Any] = field(default_factory=dict)
    deploy: Dict[str, Any] = field(default_factory=dict)
    logging: Optional[Dict[str, Any]] = None
    labels: Dict[str, str] = field(default_factory=dict)

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

        return cls(
            name=data["name"],
            image=data["image"],
            environment=envs,
            networks=networks,
            deploy=data.get("deploy", {}),
            labels=data.get("labels", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        # Convert environment from Dict[str, ComposeEnvVarSpec] to Dict[str, str]
        env_dict = {}
        for env_spec in self.environment.values():
            env_dict.update(env_spec.to_dict())

        return {
            "name": self.name,
            "image": self.image,
            "environment": env_dict,
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
