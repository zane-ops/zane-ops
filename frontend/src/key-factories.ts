import { z } from "zod";
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
    ] as const
};
