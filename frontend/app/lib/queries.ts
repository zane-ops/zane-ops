import {
  type InfiniteData,
  type QueryClient,
  infiniteQueryOptions,
  keepPreviousData,
  queryOptions,
  type skipToken,
  experimental_streamedQuery as streamedQuery
} from "@tanstack/react-query";
import { preprocess, z } from "zod";
import { zfd } from "zod-form-data";
import type { ApiResponse, RequestParams } from "~/api/client";
import { apiClient } from "~/api/client";
import {
  DEFAULT_LOGS_PER_PAGE,
  DEFAULT_QUERY_REFETCH_INTERVAL,
  DEPLOYMENT_STATUSES,
  LOGS_QUERY_REFETCH_INTERVAL,
  METRICS_TIME_RANGES
} from "~/lib/constants";
import type { Writeable } from "~/lib/types";
import { notFound } from "~/lib/utils";
import { durationToMs } from "~/utils";

export const userQueries = {
  authedUser: queryOptions({
    queryKey: ["AUTHED_USER"] as const,
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/me/", { signal });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.user) {
        return durationToMs(30, "minutes");
      }
      return false;
    }
  }),

  checkUserExistence: queryOptions({
    queryKey: ["CHECK_USER_EXISTENCE"] as const,
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/check-user-existence/", {
        signal
      });
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
    .repeatable(z.array(z.enum(["slug", "-slug", "updated_at", "-updated_at"])))
    .optional()
    .catch(undefined)
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
              ...filters
            }
          },
          signal
        });
        if (!data) {
          throw notFound(`Not found`);
        }
        return data;
      },
      placeholderData: keepPreviousData,
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
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
  serviceList: (
    slug: string,
    env_slug: string,
    filters: ProjectServiceListSearch = {}
  ) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(slug).queryKey,
        env_slug,
        "SERVICE-LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{slug}/{env_slug}/service-list/",
          {
            params: {
              query: {
                ...filters
              },
              path: {
                slug,
                env_slug
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

export const metrisSearch = z.object({
  time_range: z
    .enum(METRICS_TIME_RANGES)
    .optional()
    .default("LAST_HOUR")
    .catch("LAST_HOUR")
});

export type MetricsFilters = z.TypeOf<typeof metrisSearch>;

export const serviceQueries = {
  single: ({
    project_slug,
    service_slug,
    env_slug
  }: {
    project_slug: string;
    env_slug: string;
    service_slug: string;
  }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(project_slug).queryKey,
        env_slug,
        "SERVICE_DETAILS",
        service_slug
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{slug}/",
          {
            params: {
              path: {
                project_slug,
                slug: service_slug,
                env_slug
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
    env_slug,
    filters = {}
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    filters?: ServiceDeploymentListFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({ project_slug, service_slug, env_slug })
          .queryKey,
        "DEPLOYMENT_LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug
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
    }),
  httpLogs: ({
    project_slug,
    service_slug,
    env_slug,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    filters?: Omit<HTTPLogFilters, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...serviceQueries.single({
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "HTTP_LOGS",
        filters
      ] as const,
      queryFn: async ({ pageParam, signal, queryKey }) => {
        const allData = queryClient.getQueryData(queryKey) as InfiniteData<
          DeploymentHttpLogQueryData,
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
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/http-logs/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug
              },
              query: {
                ...filters,
                cursor,
                per_page: DEFAULT_LOGS_PER_PAGE,
                time_before: filters.time_before?.toISOString(),
                time_after: filters.time_after?.toISOString()
              }
            },
            signal
          }
        );

        let apiData: DeploymentHttpLogQueryData = {
          next: null,
          previous: null,
          results: [],
          cursor: null
        };

        if (data) {
          const next = data.next
            ? new URL(data.next).searchParams.get("cursor")
            : null;
          const previous = data.previous
            ? new URL(data.previous).searchParams.get("cursor")
            : null;
          apiData = {
            results: data.results,
            next,
            previous,
            cursor: existingData?.cursor
          };
        }

        // get cursor for initial page as its pageParam is `null`
        // we want to do so that we don't to always fetch the latest data for the initial page
        // instead what we want is to fetch from the data it starts
        if (pageParam === null && apiData.next !== null && !apiData.cursor) {
          const { data: nextPage } = await apiClient.GET(
            "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/http-logs/",
            {
              params: {
                path: {
                  project_slug,
                  service_slug,
                  env_slug
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
            apiData.cursor = new URL(nextPage.previous).searchParams.get(
              "cursor"
            );
          }
        }

        return apiData;
      },
      refetchInterval: (query) => {
        if (!query.state.data || !autoRefetchEnabled) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      getNextPageParam: ({ next }) => next,
      getPreviousPageParam: ({ previous }) => previous,
      initialPageParam: null as string | null,
      placeholderData: keepPreviousData,
      staleTime: Number.POSITIVE_INFINITY
    }),
  metrics: ({
    project_slug,
    service_slug,
    env_slug,
    filters
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    filters?: MetricsFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "METRICS",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/metrics/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug
              },
              query: {
                ...filters
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
    }),
  singleHttpLog: ({
    project_slug,
    service_slug,
    env_slug,
    request_uuid
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    request_uuid: string;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "HTTP_LOGS",
        request_uuid
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/http-logs/{request_uuid}/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                request_uuid
              }
            },
            signal
          }
        );
        return data;
      }
    }),
  filterHttpLogFields: ({
    project_slug,
    service_slug,
    env_slug,
    field,
    value
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    field: RequestParams<
      "get",
      "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/http-logs/fields/"
    >["field"];
    value: string;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "HTTP_LOG_FIELDS",
        field,
        value
      ],
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/http-logs/fields/",
          {
            signal,
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug
              },
              query: {
                field,
                value
              }
            }
          }
        );
        return data ?? [];
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

export const deploymentQueries = {
  single: ({
    project_slug,
    service_slug,
    env_slug,
    deployment_hash
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
  }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(project_slug).queryKey,
        env_slug,
        "SERVICE_DETAILS",
        service_slug,
        "DEPLOYMENTS",
        deployment_hash
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
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
    env_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    filters?: Omit<DeploymentLogFilters, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          env_slug,
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
         * However if we have the data in the cache and next is `null`,
         * it means that that page is the last page with the most recent data
         * and the next time we fetch it, there might be more data available.
         * Inspired by: https://github.com/TanStack/query/discussions/5921
         */
        if (existingData?.next) {
          return existingData;
        }

        /**
         * when we issue a refetch, for all pages we fetched via `fetchPreviousPage` starting from the second page,
         * tanstack query will use the `next` page pointer of the previous to refetch them,
         * so we check if we already have it.
         * In the docs, it's so that the data the pointers aren't stale, but we don't have that issue
         * since the log data is immutable.
         * ref: https://tanstack.com/query/latest/docs/framework/react/guides/infinite-queries#what-happens-when-an-infinite-query-needs-to-be-refetched
         */
        const existingDataIndex = allData?.pages.findIndex(
          (_, index) => allData?.pages[index].next === pageParam
        );
        if (!existingData && existingDataIndex > -1) {
          const nextPage = allData.pages[existingDataIndex + 1];
          if (nextPage) {
            return nextPage;
          }
        }

        // the actual request
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/runtime-logs/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash
              },
              query: {
                per_page: DEFAULT_LOGS_PER_PAGE,
                cursor: pageParam ?? existingData?.cursor ?? undefined,
                ...filters,
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
          // we reverse the results and reverse the page pointers (next/previous) because
          // the data from the API is in reverse order of traversal and timestamp.
          // Reversing them allows us to reorder the data in the ascending order as it is shown in the UI
          apiData = {
            results: data.results.toReversed(),
            next: data?.previous ?? null,
            previous: data?.next ?? null,
            cursor: existingData?.cursor
          };
        }

        // get cursor for initial page as its pageParam is `null`
        // we want to do that because we don't to always fetch the latest data for the initial page
        // instead what we want is to fetch from the time it starts
        if (
          pageParam === null &&
          !apiData.cursor &&
          !apiData.next &&
          apiData.results.length > 0
        ) {
          const oldestLog = apiData.results[0];
          const cursor = { sort: [oldestLog.timestamp], order: "asc" };
          apiData.cursor = btoa(JSON.stringify(cursor));
        }

        return apiData;
      },
      getNextPageParam: ({ next }) => next,
      getPreviousPageParam: ({ previous }) => previous,
      initialPageParam: null as string | null,
      refetchInterval: (query) => {
        if (!query.state.data || !autoRefetchEnabled) {
          return false;
        }
        return LOGS_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData,
      staleTime: Number.POSITIVE_INFINITY
    }),
  buildLogs: ({
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    queryClient
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
        }).queryKey,
        "BUILD_LOGS"
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
         * However if we have the data in the cache and next is `null`,
         * it means that that page is the last page with the most recent data
         * and the next time we fetch it, there might be more data available.
         * Inspired by: https://github.com/TanStack/query/discussions/5921
         */
        if (existingData?.next) {
          return existingData;
        }

        /**
         * when we issue a refetch, for all pages we fetched via `fetchPreviousPage` starting from the second page,
         * tanstack query will use the `next` page pointer of the previous to refetch them,
         * so we check if we already have it.
         * In the docs, it's so that the data the pointers aren't stale, but we don't have that issue
         * since the log data is immutable.
         * ref: https://tanstack.com/query/latest/docs/framework/react/guides/infinite-queries#what-happens-when-an-infinite-query-needs-to-be-refetched
         */
        const existingDataIndex = allData?.pages.findIndex(
          (_, index) => allData?.pages[index].next === pageParam
        );
        if (!existingData && existingDataIndex > -1) {
          const nextPage = allData.pages[existingDataIndex + 1];
          if (nextPage) {
            return nextPage;
          }
        }

        // the actual request
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/build-logs/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash
              },
              query: {
                per_page: DEFAULT_LOGS_PER_PAGE,
                cursor: pageParam ?? existingData?.cursor ?? undefined
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
          // we reverse the results and reverse the page pointers (next/previous) because
          // the data from the API is in reverse order of traversal and timestamp.
          // Reversing them allows us to reorder the data in the ascending order as it is shown in the UI
          apiData = {
            results: data.results.toReversed(),
            next: data?.previous ?? null,
            previous: data?.next ?? null,
            cursor: existingData?.cursor
          };
        }

        // get cursor for initial page as its pageParam is `null`
        // we want to do that because we don't to always fetch the latest data for the initial page
        // instead what we want is to fetch from the time it starts
        if (
          pageParam === null &&
          !apiData.cursor &&
          !apiData.next &&
          apiData.results.length > 0
        ) {
          const oldestLog = apiData.results[0];
          const cursor = { sort: [oldestLog.timestamp], order: "asc" };
          apiData.cursor = btoa(JSON.stringify(cursor));
        }

        return apiData;
      },
      getNextPageParam: ({ next }) => next,
      getPreviousPageParam: ({ previous }) => previous,
      initialPageParam: null as string | null,
      refetchInterval: (query) => {
        if (!query.state.data || !autoRefetchEnabled) {
          return false;
        }
        return LOGS_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData,
      staleTime: Number.POSITIVE_INFINITY
    }),
  metrics: ({
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    filters
  }: {
    project_slug: string;
    deployment_hash: string;
    service_slug: string;
    env_slug: string;
    filters?: MetricsFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
        }).queryKey,
        "METRICS",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/metrics/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash
              },
              query: {
                ...filters
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
    }),
  httpLogs: ({
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    filters?: Omit<HTTPLogFilters, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
        }).queryKey,
        "HTTP_LOGS",
        filters
      ] as const,
      queryFn: async ({ pageParam, signal, queryKey }) => {
        const allData = queryClient.getQueryData(queryKey) as InfiniteData<
          DeploymentHttpLogQueryData,
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
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/http-logs/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash
              },
              query: {
                ...filters,
                cursor,
                per_page: DEFAULT_LOGS_PER_PAGE,
                time_before: filters.time_before?.toISOString(),
                time_after: filters.time_after?.toISOString()
              }
            },
            signal
          }
        );

        let apiData: DeploymentHttpLogQueryData = {
          next: null,
          previous: null,
          results: [],
          cursor: null
        };

        if (data) {
          const next = data.next
            ? new URL(data.next).searchParams.get("cursor")
            : null;
          const previous = data.previous
            ? new URL(data.previous).searchParams.get("cursor")
            : null;
          apiData = {
            results: data.results,
            next,
            previous,
            cursor: existingData?.cursor
          };
        }

        // get cursor for initial page as its pageParam is `null`
        // we want to do so that we don't to always fetch the latest data for the initial page
        // instead what we want is to fetch from the data it starts
        if (pageParam === null && apiData.next !== null && !apiData.cursor) {
          const { data: nextPage } = await apiClient.GET(
            "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/http-logs/",
            {
              params: {
                path: {
                  project_slug,
                  service_slug,
                  env_slug,
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
            apiData.cursor = new URL(nextPage.previous).searchParams.get(
              "cursor"
            );
          }
        }

        return apiData;
      },
      refetchInterval: (query) => {
        if (!query.state.data || !autoRefetchEnabled) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      getNextPageParam: ({ next }) => next,
      getPreviousPageParam: ({ previous }) => previous,
      initialPageParam: null as string | null,
      placeholderData: keepPreviousData,
      staleTime: Number.POSITIVE_INFINITY
    }),
  singleHttpLog: ({
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    request_uuid
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    request_uuid: string;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
        }).queryKey,
        "HTTP_LOGS",
        request_uuid
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/http-logs/{request_uuid}/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash,
                request_uuid
              }
            },
            signal
          }
        );
        return data;
      }
    }),
  filterHttpLogFields: ({
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    field,
    value
  }: {
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    field: RequestParams<
      "get",
      "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/http-logs/fields/"
    >["field"];
    value: string;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
        }).queryKey,
        "HTTP_LOG_FIELDS",
        field,
        value
      ],
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/http-logs/fields/",
          {
            signal,
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash
              },
              query: {
                field,
                value
              }
            }
          }
        );
        return data ?? [];
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
      if (!data) throw new Error("Unknown error with the API");
      return data;
    },
    staleTime: Number.MAX_SAFE_INTEGER
  })
};

type DeploymentLogQueryData = Pick<
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

type DeploymentHttpLogQueryData = Pick<
  NonNullable<
    ApiResponse<
      "get",
      "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/http-logs/"
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

export const resourceQueries = {
  search: (query?: string) =>
    queryOptions({
      queryKey: ["RESOURCES", query] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/search-resources/", {
          params: {
            query: {
              query: (query ?? "").trim()
            }
          },
          signal
        });
      },
      enabled: (query ?? "").trim().length > 0
    })
};

export type LatestRelease = {
  tag: string;
  url: string;
};

export const versionQueries = {
  latest: queryOptions<LatestRelease | null>({
    queryKey: ["LATEST_RELEASE"] as const,
    queryFn: async ({ signal }) => {
      try {
        const response = await fetch(
          "https://cdn.zaneops.dev/api/latest-release",
          { signal }
        );
        return response.json() as Promise<LatestRelease>;
      } catch (error) {
        return null;
      }
    },
    refetchInterval: durationToMs(1, "hours")
  })
};

export const sshKeysQueries = {
  list: queryOptions({
    queryKey: ["SSH_KEYS"] as const,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/shell/ssh-keys/", {
        signal
      });
      if (!data) {
        throw notFound("Oops !");
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

export const gitAppsQueries = {
  list: queryOptions({
    queryKey: ["GIT_APPS"] as const,
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/connectors/list/", {
        signal
      });
      if (!data) {
        throw notFound("Oops !");
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
  single: (id: string) =>
    queryOptions({
      queryKey: ["GIT_APPS", id] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/connectors/{id}/", {
          params: { path: { id } },
          signal
        });
        if (!data) {
          throw notFound("Oops !");
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
  github: (id: string) =>
    queryOptions({
      queryKey: [...gitAppsQueries.list.queryKey, "GITHUB", id] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/connectors/github/{id}/", {
          signal,
          params: {
            path: { id }
          }
        });
        if (!data) {
          throw notFound("This GitHub app does not exists.");
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
  gitlab: (id: string) =>
    queryOptions({
      queryKey: [...gitAppsQueries.list.queryKey, "GITLAB", id] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/connectors/gitlab/{id}/", {
          signal,
          params: {
            path: { id }
          }
        });
        if (!data) {
          throw notFound("This Gitlab app does not exists.");
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
  repositories: (
    id: string,
    filters: { query?: string; gitClient?: "github" | "gitlab" } = {}
  ) => {
    async function fetchRepositories({
      signal,
      shouldResyncRepos
    }: { signal: AbortSignal; shouldResyncRepos?: boolean }) {
      return apiClient.GET("/api/connectors/{id}/repositories/", {
        params: {
          path: {
            id
          },
          query: {
            // do not pass `filters.query` if empty
            query: filters.query?.trim() ? filters.query.trim() : undefined,
            resync_repos: shouldResyncRepos
          }
        },
        signal
      });
    }

    return queryOptions({
      queryKey: [
        ...gitAppsQueries.single(id).queryKey,
        "REPOSITORIES",
        filters
      ] as const,
      queryFn: streamedQuery({
        refetchMode: "replace",
        queryFn: async function* ({ signal }) {
          const { data } = await fetchRepositories({ signal });

          if (!data) {
            throw notFound("Oops !");
          }

          if (filters.gitClient === "github") return data;

          yield data;
          return await fetchRepositories({ signal, shouldResyncRepos: true });
        }
      }),
      placeholderData: keepPreviousData
    });
  }
};

export type SSHKey = NonNullable<
  ApiResponse<"get", "/api/shell/ssh-keys/">
>[number];

export type GitApp = NonNullable<ApiResponse<"get", "/api/connectors/{id}/">>;

export type GithubApp = ApiResponse<"get", "/api/connectors/github/{id}/">;
export type GitlabApp = ApiResponse<"get", "/api/connectors/gitlab/{id}/">;

export type GitRepository = NonNullable<
  ApiResponse<"get", "/api/connectors/{id}/repositories/">
>[number];
