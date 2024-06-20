import { z } from "zod";
export const userKeys = {
  authedUser: ["AUTHED_USER"] as const,
};

export const projectSearchSchema = z.object({
  slug: z.string().optional().catch(""),
  page: z.number().optional().catch(1),
  per_page: z.number().optional().catch(10),
  sort_by: z
    .array(z.enum(["slug", "-slug", "updated_at", "-updated_at"]))
    .optional()
    .catch(["-updated_at"]),
  status: z.enum(["active", "archived"]).optional().catch("active"),
});
export type ProjectSearch = z.infer<typeof projectSearchSchema>;

export const projectKeys = {
  list: (filters: ProjectSearch) => ["PROJECT_LIST", filters] as const,
  archived: (filters: ProjectSearch) => ["PROJECT_LIST", filters] as const,
};
