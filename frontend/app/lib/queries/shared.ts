import { preprocess, z } from "zod";
import { zfd } from "zod-form-data";
import type { ApiResponse } from "~/api/client";
import type { Writeable } from "~/lib/types";

/**
 * Base query key for all resources scoped to a workspace.
 * The current workspace is server-side session state, so the react-query
 * cache must be partitioned by `workspaceId` to avoid leaking data across
 * workspaces.
 */
export const workspaceKey = (workspaceId: string) =>
  ["WORKSPACE", workspaceId] as const;

export const LOG_LEVELS = ["INFO", "ERROR"] as const;
export const LOG_SOURCES = ["SYSTEM", "SERVICE"] as const;

export const HTTP_LOG_SOURCES = [
  "SERVICE",
  "COMPOSE_STACK",
  "BUILD_REGISTRY",
  "ZANE_OPS_API",
  "ZANE_OPS_FRONTEND",
  "UNKNOWN"
] as const;

export const HTTP_LOG_SOURCE_LABELS: Record<
  (typeof HTTP_LOG_SOURCES)[number],
  string
> = {
  SERVICE: "Service",
  COMPOSE_STACK: "Compose stack",
  BUILD_REGISTRY: "Build registry",
  ZANE_OPS_API: "ZaneOps API",
  ZANE_OPS_FRONTEND: "ZaneOps Frontend",
  UNKNOWN: "Unknown"
};

export const REQUEST_METHODS = [
  "DELETE",
  "GET",
  "HEAD",
  "OPTIONS",
  "PATCH",
  "POST",
  "PUT"
] as const;

export const deploymentLogSearchSchema = zfd.formData({
  level: zfd.repeatable(
    z
      .array(z.enum(LOG_LEVELS))
      .optional()
      .catch(LOG_LEVELS as Writeable<typeof LOG_LEVELS>)
  ),
  time_before: z.coerce.date().optional().catch(undefined),
  time_after: z.coerce.date().optional().catch(undefined),
  content: z.string().optional(),
  query: z.string().optional(),
  isMaximized: preprocess(
    (arg) => arg === "true",
    z.coerce.boolean().optional().catch(false)
  ),
  context: z.coerce.number().optional().catch(undefined),
  context_lines: z.coerce.number().min(5).optional().catch(undefined)
});

export type DeploymentLogFilters = z.infer<typeof deploymentLogSearchSchema>;

export const httpLogSearchSchema = zfd.formData({
  time_before: z.coerce.date().optional().catch(undefined),
  time_after: z.coerce.date().optional().catch(undefined),
  request_method: zfd
    .repeatable(z.array(z.enum(REQUEST_METHODS)).optional().catch(undefined))
    .transform((val) => (val?.length === 0 ? undefined : val)),
  request_query: z.string().optional(),
  request_path: zfd
    .repeatable(z.array(z.string()).optional().catch(undefined))
    .transform((val) => (val?.length === 0 ? undefined : val)),
  request_country_code: zfd
    .repeatable(z.array(z.string()).optional().catch(undefined))
    .transform((val) => (val?.length === 0 ? undefined : val)),
  request_host: zfd
    .repeatable(z.array(z.string()).optional().catch(undefined))
    .transform((val) => (val?.length === 0 ? undefined : val)),
  request_ip: zfd
    .repeatable(z.array(z.string().ip()).optional().catch(undefined))
    .transform((val) => (val?.length === 0 ? undefined : val)),
  request_user_agent: zfd
    .repeatable(z.array(z.string()).optional().catch(undefined))
    .transform((val) => (val?.length === 0 ? undefined : val)),
  request_id: z.string().uuid().optional().catch(undefined),
  status: zfd
    .repeatable(
      z
        .array(z.string())
        .transform((array) =>
          array.filter(
            (val) =>
              val.match(/\dxx/) || (!Number.isNaN(val) && Number(val) > 0)
          )
        )
        .optional()
        .catch(undefined)
    )
    .transform((val) => (val?.length === 0 ? undefined : val)),
  isMaximized: preprocess(
    (arg) => arg === "true",
    z.coerce.boolean().optional().catch(false)
  ),
  sort_by: zfd
    .repeatable(
      z.array(
        z.enum(["time", "-time", "request_duration_ns", "-request_duration_ns"])
      )
    )
    .optional()
    .catch(undefined)
});

export type HTTPLogFilters = z.infer<typeof httpLogSearchSchema>;
export type DeploymentLogQueryData = Pick<
  NonNullable<
    ApiResponse<
      "get",
      "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/runtime-logs/"
    >
  >,
  "next" | "previous" | "results"
> & {
  cursor?: string | null;
};

export type HttpLogQueryData = Pick<
  NonNullable<ApiResponse<"get", "/api/http-logs/">>,
  "next" | "previous" | "results"
> & {
  cursor?: string | null;
};

export const paginationListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional()
});
