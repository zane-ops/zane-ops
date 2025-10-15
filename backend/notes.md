### Docker container registries


Process for building:
1- Creating a `config.json` in the /tmp/<base>/.docker folder of the build
    with the content: `{"auths":{"<registry_url>":{"auth":"base64_encode(<username>:<password>)"}}}`
2- DOCKER_CONFIG=/tmp/<base>/.docker docker login ghcr.io &&  DOCKER_CONFIG=/tmp/<base>/.docker docker buildx build --push -t <registry_url>/<username>/<package> .
   
**Issues:** 
1. with gitlab: the path is not assured to always be `<username>/<package>`
   on Gitlab, it needs to be `<group-or-username>/path/to/project` 
   and on GitHub, if your username is the owner of an org, they might want to use that as the base path
       
   solution(s): 
   - Use the same path as repository that is built ?
        - for services w/ git apps attached to them, we can (most of the time) use this
        - it doesn't work for services without a git app since we don't have control over them
    - ask the user to provide a base path ? 
        - in the container registry => for multiple projects, the user would have to add a container registry => not a good idea
        - in the service being built: optional field w/ the default being the path of the repo. 
            -> The problem is actually Gitlab registry, the others allow for arbitrary names with `<username>/<any-path>`, so in that case the user can choose a base path
             
2. for multi nodes: we might need to build with multi-arch so that services are also accessible on other nodes that don't have the same architecture being built or on a cluster with nodes of different CPU architectures
   solution(s): 
   - enable it on the container registry itself ? -> should be optional as it can significantly slow down builds

**Chosen flow:**

1. Credentials will be used mainly for 3 purposes:
   - pulling images for docker services
   - listing & filtering images in the image field (like we have with git repositories field)
   - used to specify an external registry for the build registry
2. Build registries will be used for:
   1. Will be required starting from next version of ZaneOps to build apps, so the user has to create one
   2. pushing built images w/ the path <project-slug-id-without-prefix>/<service-slug-id-without-prefix>:<commit_sha>
   3. allowing us to add instant rollbacks for git services
   4. Can be managed by ZaneOps (w/ the ability to specify a S3 storage backend)   
      1. When creating managed registries, zaneops will create a Credentials under the hood
      2. and create a service hosted on ZaneOps 
   
```python
def list_repositories(registry: ContainerRegistry):
    if registry.type == ContainerRegistry.RegistryType.DOCKER_HUB:
        return requests.get("https://hub.docker.com/v2/repositories/", params={"q": "..."})
    elif registry.type == ContainerRegistry.RegistryType.GHCR:
        return requests.get("https://ghcr.io/v2/_catalog", auth=(registry.username, registry.password))
    elif registry.type == ContainerRegistry.RegistryType.HARBOR:
        return requests.get(f"{registry.url}/api/v2.0/projects", auth=(registry.username, registry.password))
    else:  # GENERIC v2 registry
        return requests.get(f"{registry.url}/v2/_catalog", auth=(registry.username, registry.password))
```

## Other feature ideas

- With the managed registry: we can offer seamless rollbacks
  - how to handle cleanups ? should we even handle them at all ?
- Detect the open ports of a service and show them in the UI and make them copiable:
  - ex: from https://render.com/docs/deploy-clickhouse#connecting-to-clickhouse
    * `clickhouse:8123`	HTTP interface
    * `clickhouse:9000`	Native interface for driver libraries and clickhouse-client application
    * `clickhouse:9004`	MySQL wire protocol
      * ![clickhouse](https://render.com/docs-assets/961993646415aecffa536ab0d1c54198c95f7eb9f28ab72fddf53f84f552d610/clickhouse-shell.webp)
