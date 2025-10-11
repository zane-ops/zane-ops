from django.db import models
from typing import TYPE_CHECKING, Self
from zane_api.models.base import TimestampedModel
from shortuuid.django_fields import ShortUUIDField
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager


# Create your models here.
class ContainerRegistry(TimestampedModel):
    ID_PREFIX = "cr_"
    id = ShortUUIDField(  # type: ignore[arg-type]
        length=14,
        max_length=255,
        primary_key=True,
        prefix=ID_PREFIX,
    )

    class RegistryType(models.TextChoices):
        DOCKER_HUB = "DOCKER_HUB", _("Docker Hub")
        GITHUB = "GITHUB", _("GitHub Container Registry")
        GITLAB = "GITLAB", _("GitLab Container Registry")
        GENERIC = "GENERIC", _("Generic Docker Registry (v2 API)")

    url = models.URLField(blank=False)
    password = models.TextField(blank=False)
    username = models.CharField(max_length=1024, null=True, blank=False)
    registry_type = models.CharField(
        max_length=32,
        choices=RegistryType.choices,
        default=RegistryType.GENERIC,
    )

    def __str__(self):
        return f"ContainerRegistry(registry_type={self.RegistryType(self.registry_type).label}, url={self.url}, username={self.username})"

    # def list_repositories(registry: Self):
    #     if registry.registry_type == ContainerRegistry.RegistryType.DOCKER_HUB:
    #         return requests.get("https://hub.docker.com/v2/repositories/", params={"q": "..."})
    #     elif registry.registry_type == ContainerRegistry.RegistryType.GHCR:
    #         return requests.get("https://ghcr.io/v2/_catalog", auth=(registry.username, registry.password))
    #     elif registry.registry_type == ContainerRegistry.RegistryType.HARBOR:
    #         return requests.get(f"{registry.url}/api/v2.0/projects", auth=(registry.username, registry.password))
    #     else:  # GENERIC v2 registry
    #         return requests.get(f"{registry.url}/v2/_catalog", auth=(registry.username, registry.password))


"""
Process for building:
1- Creating a `config.json` in the /tmp/<base>/.docker folder of the build
    with the content: `{"auths":{"<registry_url>":{"auth":"base64_encode(<username>:<password>)"}}}`
2- DOCKER_CONFIG=/tmp/<base>/.docker docker login ghcr.io &&  DOCKER_CONFIG=/tmp/<base>/.docker docker buildx build --push -t <registry_url>/<username>/<package> .
   
Issues: 
    1- with gitlab: the path is not assured to always be `<username>/<package>`
       on Gitlab, it needs to be `<group-or-username>/path/to/project` 
       and on GitHub, if your username is the owner of an org, they might want to use that as the base path
       
       solution(s): 
        - Use the same path as repository that is built ?
            - for services w/ git apps attached to them, we can (most of the time) use this
            - but it's a little complicated 
        - ask the user to provide a base path ? 
            => for multiple projects, the user would have to add a container registry => not a good idea
    
    2- for multi nodes: we might need to build with multi-arch so that services are also accessible on other nodes
       solution(s): maybe enable it on the container registry itself ?
"""
