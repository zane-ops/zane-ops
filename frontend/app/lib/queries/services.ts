import {
  type InfiniteData,
  type QueryClient,
  infiniteQueryOptions,
  keepPreviousData,
  queryOptions
} from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import type { RequestParams } from "~/api/client";
import { apiClient } from "~/api/client";
import {
  DEFAULT_LOGS_PER_PAGE,
  DEFAULT_QUERY_REFETCH_INTERVAL,
  DEPLOYMENT_STATUSES,
  METRICS_TIME_RANGES
} from "~/lib/constants";
import type { HTTPLogFilters, HttpLogQueryData } from "~/lib/queries/logs";
import { projectQueries } from "~/lib/queries/projects";
import type { Writeable } from "~/lib/types";
import { notFound } from "~/lib/utils";

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
    workspaceId,
    project_slug,
    service_slug,
    env_slug
  }: {
    workspaceId: string;
    project_slug: string;
    env_slug: string;
    service_slug: string;
  }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(workspaceId, project_slug).queryKey,
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
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    filters = {}
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    filters?: ServiceDeploymentListFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
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
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    service_id,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    workspaceId: string;
    service_id: string;
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
          workspaceId,
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        service_id,
        "HTTP_LOGS",
        filters
      ] as const,
      queryFn: async ({ pageParam, signal, queryKey }) => {
        const allData = queryClient.getQueryData(queryKey) as InfiniteData<
          HttpLogQueryData,
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

        const { data } = await apiClient.GET("/api/http-logs/", {
          params: {
            query: {
              ...filters,
              cursor,
              service_id,
              per_page: DEFAULT_LOGS_PER_PAGE,
              time_before: filters.time_before?.toISOString(),
              time_after: filters.time_after?.toISOString()
            }
          },
          signal
        });

        let apiData: HttpLogQueryData = {
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
          const { data: nextPage } = await apiClient.GET("/api/http-logs/", {
            params: {
              query: {
                ...filters,
                service_id,
                per_page: DEFAULT_LOGS_PER_PAGE,
                cursor: apiData.next,
                time_before: filters.time_before?.toISOString(),
                time_after: filters.time_after?.toISOString()
              }
            },
            signal
          });
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
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    filters
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    filters?: MetricsFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          workspaceId,
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
  detectedPorts: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "DETECTED_PORTS"
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/detected-ports/",
          {
            params: {
              path: {
                project_slug,
                service_slug,
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
    }),
  availableVolumes: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "AVAILABLE_VOLUMES_FOR_SHARING"
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/{slug}/available-volumes/",
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
          throw notFound();
        }
        return data;
      },
      placeholderData: keepPreviousData
    }),
  singleHttpLog: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    request_uuid
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    service_id: string;
    request_uuid: string;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        "HTTP_LOGS",
        request_uuid
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/http-logs/{request_uuid}/", {
          params: {
            path: {
              request_uuid
            }
          },
          signal
        });
        return data;
      }
    }),
  filterHttpLogFields: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    service_id,
    field,
    value
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    service_id: string;
    env_slug: string;
    field: RequestParams<"get", "/api/http-logs/fields/">["field"];
    value: string;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug
        }).queryKey,
        service_id,
        "HTTP_LOG_FIELDS",
        field,
        value
      ],
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/http-logs/fields/", {
          signal,
          params: {
            query: {
              field,
              value,
              service_id
            }
          }
        });
        return data ?? [];
      }
    })
};
