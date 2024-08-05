from dataclasses import dataclass


@dataclass
class HelloPayload:
    name: str


@dataclass
class DeployPayload:
    slug: str
