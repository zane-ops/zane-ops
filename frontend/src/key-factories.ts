import { z } from "zod";
import { DEPLOYMENT_STATUSES } from "~/lib/constants";
import type { Writeable } from "~/lib/types";
export const userKeys = {
  authedUser: ["AUTHED_USER"] as const
};

export const dockerHubKeys = {
  images: (query: string) => ["DOCKER_HUB_IMAGES", query] as const
};

export const projectSearchSchema = z.object({
  slug: z.string().optional().catch(""),
  page: z.number().optional().catch(1),
  per_page: z.number().optional().catch(10),
  sort_by: z
    .array(
      z.enum([
        "slug",
        "-slug",
        "updated_at",
        "-updated_at",
        "archived_at",
        "-archived_at"
      ])
    )
    .optional()
    .catch(["-updated_at"]),
  status: z.enum(["active", "archived"]).optional().catch("active")
});

export type ProjectSearch = z.infer<typeof projectSearchSchema>;

export const projectKeys = {
  list: (filters: ProjectSearch) => ["PROJECT_LIST", filters] as const,
  archived: (filters: ProjectSearch) =>
    ["ARCHIVED_PROJECT_LIST", filters] as const,
  serviceList: (slug: string, filters: ProjectServiceListSearch) =>
    [...projectKeys.single(slug), "SERVICE-LIST", filters] as const,
  single: (slug: string) => ["PROJECT_SINGLE", slug] as const
};

export const projectServiceListSearchSchema = z.object({
  query: z.string().optional().catch("")
});
export type ProjectServiceListSearch = z.infer<
  typeof projectServiceListSearchSchema
>;

export const serviceDeploymentListFilters = z.object({
  page: z.number().optional().catch(1).optional(),
  per_page: z.number().optional().catch(10).optional(),
  status: z
    .array(z.enum(DEPLOYMENT_STATUSES))
    .optional()
    .catch(DEPLOYMENT_STATUSES as Writeable<typeof DEPLOYMENT_STATUSES>),
  queued_at_before: z.coerce.date().optional().catch(undefined),
  queued_at_after: z.coerce.date().optional().catch(undefined)
});

export type ServiceDeploymentListFilters = z.infer<
  typeof serviceDeploymentListFilters
>;

export const serviceKeys = {
  single: (
    project_slug: string,
    service_slug: string,
    type: "docker" | "git"
  ) =>
    [
      ...projectKeys.single(project_slug),
      "SERVICE_DETAILS",
      type,
      service_slug
    ] as const,
  deploymentList: (
    project_slug: string,
    service_slug: string,
    type: "docker" | "git",
    filters: ServiceDeploymentListFilters
  ) =>
    [
      ...serviceKeys.single(project_slug, service_slug, type),
      "DEPLOYMENT_LIST",
      filters
    ] as const
};
