import type { ApiResponse } from "./client";

export type SSHKey = NonNullable<
  ApiResponse<"get", "/api/shell/ssh-keys/">
>[number];

export type BuildRegistry = NonNullable<
  ApiResponse<"get", "/api/registries/build-registries/{id}/">
>;
export type RegistryStorageBackend = BuildRegistry["storage_backend"];

export type SharedRegistryCredentials = NonNullable<
  ApiResponse<"get", "/api/registries/credentials/{id}/">
>;
export type ContainerRegistryType = SharedRegistryCredentials["registry_type"];

export type GitApp = NonNullable<ApiResponse<"get", "/api/connectors/{id}/">>;

export type GithubApp = ApiResponse<"get", "/api/connectors/github/{id}/">;
export type GitlabApp = ApiResponse<"get", "/api/connectors/gitlab/{id}/">;

export type GitRepository = NonNullable<
  ApiResponse<"get", "/api/connectors/{id}/repositories/">
>[number];

export type Service = ApiResponse<
  "get",
  "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/"
>;
export type ServiceBuilder = Exclude<NonNullable<Service["builder"]>, "">;

export type Project = ApiResponse<"get", "/api/projects/{slug}/">;
export type Deployment = ApiResponse<
  "get",
  "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/"
>;

export type RecentDeployment = ApiResponse<
  "get",
  "/api/recent-deployments/"
>[number];
export type PreviewTemplate = NonNullable<
  ApiResponse<
    "get",
    "/api/projects/{project_slug}/preview-templates/{template_slug}/"
  >
>;
