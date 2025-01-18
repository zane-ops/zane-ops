import {
  type InfiniteData,
  type QueryClient,
  infiniteQueryOptions,
  keepPreviousData,
  queryOptions,
  type skipToken
} from "@tanstack/react-query";
import { preprocess, z } from "zod";
import { zfd } from "zod-form-data";
import { type ApiResponse, apiClient } from "~/api/client";
import {
  DEFAULT_LOGS_PER_PAGE,
  DEFAULT_QUERY_REFETCH_INTERVAL,
  DEPLOYMENT_STATUSES
} from "~/lib/constants";
import type { Writeable } from "~/lib/types";
import { notFound } from "~/lib/utils";

const THIRTY_MINUTES = 30 * 60 * 1000; // in milliseconds

export const userQueries = {
  authedUser: queryOptions({
    queryKey: ["AUTHED_USER"] as const,
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/me/", { signal });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.user) {
        return THIRTY_MINUTES;
      }
      return false;
    }
  })
};

export const dockerHubQueries = {
  images: (query: string) =>
    queryOptions({
      queryKey: ["DOCKER_HUB_IMAGES", query] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/docker/image-search/", {
          params: {
            query: {
              q: query.trim()
            }
          },
          signal
        });
      },
      enabled: query.trim().length > 0
    })
};

export const projectSearchSchema = zfd.formData({
  slug: z.string().optional().catch(undefined),
  page: zfd.numeric().optional().catch(undefined),
  per_page: zfd.numeric().optional().catch(undefined),
  sort_by: zfd
    .repeatable(
      z.array(
        z.enum([
          "slug",
          "-slug",
          "updated_at",
          "-updated_at",
          "archived_at",
          "-archived_at"
        ])
      )
    )
    .optional()
    .catch(undefined),
  status: z.enum(["active", "archived"]).optional().catch(undefined)
});

export type ProjectSearch = z.infer<typeof projectSearchSchema>;

export const projectQueries = {
  list: (filters: ProjectSearch = {}) =>
    queryOptions({
      queryKey: ["PROJECT_LIST", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/projects/", {
          params: {
            query: {
              ...filters,
              sort_by: filters.sort_by?.filter(
                (criteria) =>
                  criteria !== "-archived_at" && criteria !== "archived_at"
              )
            }
          },
          signal
        });
        return data;
      },
      placeholderData: keepPreviousData,
      enabled: filters.status !== "archived",
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    }),
  archived: (filters: ProjectSearch) =>
    queryOptions({
      queryKey: ["ARCHIVED_PROJECT_LIST", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/archived-projects/", {
          params: {
            query: {
              ...filters,
              sort_by: filters.sort_by?.filter(
                (criteria) =>
                  criteria !== "-updated_at" && criteria !== "updated_at"
              )
            }
          },
          signal
        });
        return data;
      },
      enabled: filters.status === "archived"
    }),
  single: (slug: string) =>
    queryOptions({
      queryKey: ["PROJECT_SINGLE", slug] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/projects/{slug}/", {
          params: {
            path: {
              slug
            }
          },
          signal
        });
        if (!data) {
          throw notFound(
            `The project \`${slug}\` does not exist on this server`
          );
        }
        return data;
      },
      placeholderData: keepPreviousData
    }),
  serviceList: (slug: string, filters: ProjectServiceListSearch = {}) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(slug).queryKey,
        "SERVICE-LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{slug}/service-list/",
          {
            params: {
              query: {
                ...filters
              },
              path: {
                slug
              }
            },
            signal
          }
        );

        if (!data) {
          throw notFound();
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    })
};

export const projectServiceListSearchSchema = z.object({
  query: z.string().optional().catch("")
});
export type ProjectServiceListSearch = z.infer<
  typeof projectServiceListSearchSchema
>;

export const serviceDeploymentListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional(),
  status: zfd.repeatable(
    z
      .array(z.enum(DEPLOYMENT_STATUSES))
      .optional()
      .catch(DEPLOYMENT_STATUSES as Writeable<typeof DEPLOYMENT_STATUSES>)
  ),
  queued_at_before: z.coerce.date().optional().catch(undefined),
  queued_at_after: z.coerce.date().optional().catch(undefined)
});

export type ServiceDeploymentListFilters = z.infer<
  typeof serviceDeploymentListFilters
>;

export type DockerService = ApiResponse<
  "get",
  "/api/projects/{project_slug}/service-details/docker/{service_slug}/"
>;

export const serviceQueries = {
  single: ({
    project_slug,
    service_slug,
    type = "docker"
  }: { project_slug: string; service_slug: string; type?: "docker" | "git" }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(project_slug).queryKey,
        "SERVICE_DETAILS",
        type,
        service_slug
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/",
          {
            params: {
              path: {
                project_slug,
                service_slug
              }
            },
            signal
          }
        );

        if (!data) {
          throw notFound(
            `The service \`${service_slug}\` doesn't exist in this project.`
          );
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    }),
  deploymentList: ({
    project_slug,
    service_slug,
    type = "docker",
    filters = {}
  }: {
    project_slug: string;
    service_slug: string;
    type?: "docker" | "git";
    filters?: ServiceDeploymentListFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({ project_slug, service_slug, type }).queryKey,
        "DEPLOYMENT_LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/",
          {
            params: {
              path: {
                project_slug,
                service_slug
              },
              query: {
                ...filters,
                queued_at_after: filters.queued_at_after?.toISOString(),
                queued_at_before: filters.queued_at_before?.toISOString()
              }
            },
            signal
          }
        );

        if (!data) {
          throw notFound();
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    })
};

export const LOG_LEVELS = ["INFO", "ERROR"] as const;
export const LOG_SOURCES = ["SYSTEM", "SERVICE"] as const;
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
  source: zfd.repeatable(
    z
      .array(z.enum(LOG_SOURCES))
      .optional()
      .catch(LOG_SOURCES as Writeable<typeof LOG_SOURCES>)
  ),
  time_before: z.coerce.date().optional().catch(undefined),
  time_after: z.coerce.date().optional().catch(undefined),
  content: z.string().optional(),
  query: z.string().optional(),
  isMaximized: preprocess(
    (arg) => arg === "true",
    z.coerce.boolean().optional().catch(false)
  )
});

export type DeploymentLogFilters = z.infer<typeof deploymentLogSearchSchema>;

export const deploymentHttpLogSearchSchema = zfd.formData({
  time_before: z.coerce.date().optional().catch(undefined),
  time_after: z.coerce.date().optional().catch(undefined),
  request_method: zfd.repeatable(
    z
      .array(z.enum(REQUEST_METHODS))
      .optional()
      .catch(REQUEST_METHODS as Writeable<typeof REQUEST_METHODS>)
  ),
  request_path: z.string().optional(),
  request_host: z.string().optional(),
  request_ip: z.string().ip().optional().catch(undefined),
  request_user_agent: z.string().ip().optional().catch(undefined),
  request_id: z.string().uuid().optional().catch(undefined),
  status: zfd.numeric().optional().catch(undefined),
  isMaximized: preprocess(
    (arg) => arg === "true",
    z.coerce.boolean().optional().catch(false)
  )
});

export type DeploymentHTTPLogFilters = z.infer<
  typeof deploymentHttpLogSearchSchema
>;

export const deploymentQueries = {
  single: ({
    project_slug,
    service_slug,
    deployment_hash
  }: {
    project_slug: string;
    service_slug: string;
    deployment_hash: string;
  }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(project_slug).queryKey,
        "SERVICE_DETAILS",
        service_slug,
        "DEPLOYMENTS",
        deployment_hash
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/{deployment_hash}/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                deployment_hash
              }
            },
            signal
          }
        );
        if (!data) {
          throw notFound(`This deployment does not exist in this service.`);
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    }),
  logs: ({
    project_slug,
    service_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    project_slug: string;
    service_slug: string;
    deployment_hash: string;
    filters?: Omit<DeploymentLogFitlers, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          deployment_hash
        }).queryKey,
        "RUNTIME_LOGS",
        filters
      ],
      queryFn: async ({ pageParam, signal, queryKey }) => {
        const allData = queryClient.getQueryData(queryKey) as InfiniteData<
          DeploymentLogQueryData,
          string | null
        >;
        const existingData = allData?.pages.find(
          (_, index) => allData?.pageParams[index] === pageParam
        );

        /**
         * We reuse the data in the query as we are sure this page is immutable,
         * And we don't want to refetch the same logs that we have already fetched.
         *
         * However if we have the data in the cache and previous is `null`,
         * it means that that page is the last and the next time we fetch it,
         * it might have more data.
         * Inspired by: https://github.com/TanStack/query/discussions/5921
         */
        if (existingData?.previous) {
          return existingData;
        }

        let cursor = pageParam ?? undefined;
        if (existingData?.cursor) {
          cursor = existingData.cursor;
        }

        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/{deployment_hash}/logs/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                deployment_hash
              },
              query: {
                ...filters,
                per_page: DEFAULT_LOGS_PER_PAGE,
                cursor,
                time_before: filters.time_before?.toISOString(),
                time_after: filters.time_after?.toISOString()
              }
            },
            signal
          }
        );

        let apiData: DeploymentLogQueryData = {
          next: null,
          previous: null,
          results: [],
          cursor: null
        };

        if (data) {
          apiData = {
            results: data.results,
            next: data?.next ?? null,
            previous: data?.previous ?? null,
            cursor: existingData?.cursor
          };
        }

        // get cursor for initial page as its pageParam is `null`
        // we want to do so that we don't to always fetch the latest data for the initial page
        // instead what we want is to fetch from the data it starts
        if (pageParam === null && apiData.next !== null && !apiData.cursor) {
          const { data: nextPage } = await apiClient.GET(
            "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/{deployment_hash}/logs/",
            {
              params: {
                path: {
                  project_slug,
                  service_slug,
                  deployment_hash
                },
                query: {
                  ...filters,
                  per_page: DEFAULT_LOGS_PER_PAGE,
                  cursor: apiData.next,
                  time_before: filters.time_before?.toISOString(),
                  time_after: filters.time_after?.toISOString()
                }
              },
              signal
            }
          );
          if (nextPage?.previous) {
            apiData.cursor = nextPage.previous;
          }
        }

        return apiData;
      },
      // we use the inverse of the cursors we get from the API
      // because the API order them by time but in descending order,
      // so the next page is actually the oldest,
      // we flip it here because we want to keep it consistent with our UI
      getNextPageParam: ({ previous }) => previous,
      getPreviousPageParam: ({ next }) => next,
      initialPageParam: null as string | null,
      refetchInterval: (query) => {
        if (!query.state.data || !autoRefetchEnabled) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData,
      staleTime: Number.POSITIVE_INFINITY
    }),
  httpLogs: ({
    project_slug,
    service_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    project_slug: string;
    service_slug: string;
    deployment_hash: string;
    filters?: Omit<DeploymentHTTPLogFilters, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          deployment_hash
        }).queryKey,
        "HTTP_LOGS"
      ] as const,
      queryFn: async ({ pageParam, signal, queryKey }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/{deployment_hash}/http-logs/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                deployment_hash
              },
              query: {
                ...filters,
                per_page: DEFAULT_LOGS_PER_PAGE,
                // cursor,
                time_before: filters.time_before?.toISOString(),
                time_after: filters.time_after?.toISOString()
              }
            },
            signal
          }
        );
        if (!data) throw notFound();
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data || !autoRefetchEnabled) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      getNextPageParam: ({ next }) => {
        if (next) {
          const url = new URL(next);
          return url.searchParams.get("cursor");
        }
        return null;
      },
      getPreviousPageParam: ({ previous }) => {
        if (previous) {
          const url = new URL(previous);
          return url.searchParams.get("cursor");
        }
        return null;
      },
      initialPageParam: null as string | null,
      placeholderData: keepPreviousData,
      staleTime: Number.POSITIVE_INFINITY
    }),

  singleHttpLog: ({
    project_slug,
    service_slug,
    deployment_hash,
    request_uuid
  }: {
    project_slug: string;
    service_slug: string;
    deployment_hash: string;
    request_uuid: string;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          deployment_hash
        }).queryKey,
        "HTTP_LOGS",
        request_uuid
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/{deployment_hash}/http-logs/{request_uuid}/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                deployment_hash,
                request_uuid
              }
            },
            signal
          }
        );
        return data;
      }
    })
};

export const serverQueries = {
  settings: queryOptions({
    queryKey: ["APP_SETTINGS"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/settings/");
      return data;
    },
    staleTime: Number.MAX_SAFE_INTEGER
  }),
  resourceLimits: queryOptions({
    queryKey: ["SERVICE_RESOURCE_LIMITS"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/server/resource-limits/");
      return data;
    },
    staleTime: Number.MAX_SAFE_INTEGER
  })
};

type DeploymentLogQueryData = Pick<
  NonNullable<
    ApiResponse<
      "get",
      "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/{deployment_hash}/logs/"
    >
  >,
  "next" | "previous" | "results"
> & {
  cursor?: string | null;
};

export type DeploymentLog = Awaited<
  ReturnType<
    NonNullable<
      Exclude<
        ReturnType<typeof deploymentQueries.logs>["queryFn"],
        typeof skipToken
      >
    >
  >
>["results"][number];

export type HttpLog = Awaited<
  ReturnType<
    NonNullable<
      Exclude<
        ReturnType<typeof deploymentQueries.httpLogs>["queryFn"],
        typeof skipToken
      >
    >
  >
>["results"][number];

export type DeploymentLogFitlers = z.infer<typeof deploymentLogSearchSchema>;

export const resourceQueries = {
  search: (query: string) =>
    queryOptions({
      queryKey: ["RESOURCES", query] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/search-resources/", {
          params: {
            query: {
              query: query.trim()
            }
          },
          signal
        });
      },
      enabled: query.trim().length > 0
    })
};
