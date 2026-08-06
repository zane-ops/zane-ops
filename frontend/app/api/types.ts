import type { ApiResponse, RequestParams } from "./client";

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

export type AuthedUserResponse = ApiResponse<"get", "/api/auth/me/">;

export type WorkspaceMembership = ApiResponse<
  "get",
  "/api/workspaces/list/"
>[number];

export type SimpleWorkspace = ApiResponse<"get", "/api/workspace/">;

export type WorkspaceMember = ApiResponse<
  "get",
  "/api/workspace/members/"
>["results"][number];

export type WorkspaceInvitation = ApiResponse<
  "get",
  "/api/workspace/invitations/"
>["results"][number];

export type WorkspaceInvitationLink = ApiResponse<
  "get",
  "/api/workspace/invitations/{token}/"
>;

export type WorkspaceRoleName = WorkspaceMember["role_name"];
export type UserRole = WorkspaceRoleName | "ServerAdmin";
export type WorkspaceRoleValue = WorkspaceMember["role"];

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
export type ComposeStack = ApiResponse<
  "get",
  "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/"
>;

export type ComposeStackTask =
  ComposeStack["services"][string]["tasks"][number];

export type ComposeStackService = ComposeStack["services"][string];

export type ComposeStackDeployment = ApiResponse<
  "get",
  "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deployments/{hash}/"
>;

export type ServerSettings = ApiResponse<"get", "/api/settings/">;
export type SearchResource = ApiResponse<
  "get",
  "/api/search-resources/"
>[number];

export type DeploymentLog = ApiResponse<
  "get",
  "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/runtime-logs/"
>["results"][number];

export type HttpLog = ApiResponse<"get", "/api/http-logs/{request_uuid}/">;

export type User = ApiResponse<"get", "/api/console/users/{id}/">;

export type PasswordResetToken = ApiResponse<
  "get",
  "/api/console/password-tokens/{id}"
>;

export type HttpLogFilterField = RequestParams<
  "get",
  "/api/http-logs/fields/"
>["field"];

export type TemplateDocument = {
  id: string;
  name: string;
  description: string;
  url: string;
  tags: string[];
  logoUrl: string;
};

export type TextMatchInfo = {
  best_field_score: string;
  best_field_weight: number;
  fields_matched: number;
  num_tokens_dropped: number;
  score: string;
  tokens_matched: number;
  typo_prefix_score: number;
};

export type TemplateHit = {
  document: TemplateDocument;
  highlight: Record<string, never>;
  highlights: unknown[];
  text_match: number;
  text_match_info: TextMatchInfo;
};

export type SearchRequestParams = {
  collection_name: string;
  first_q: string;
  per_page: number;
  q: string;
};

export type TemplateSearchAPIResponse = {
  facet_counts: unknown[];
  found: number;
  hits: TemplateHit[];
  out_of: number;
  page: number;
  request_params: SearchRequestParams;
  search_cutoff: boolean;
  search_time_ms: number;
};

export type TemplateDetailsApiResponse = {
  id: string;
  name: string;
  description: string;
  tags: string[];
  logoUrl: string;
  githubUrl: string;
  docsUrl: string;
  websiteUrl: string;
  url: string;
  compose: string;
};
