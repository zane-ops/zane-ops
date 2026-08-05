import {
  type InfiniteData,
  type QueryClient,
  infiniteQueryOptions,
  keepPreviousData,
  queryOptions
} from "@tanstack/react-query";
import { preprocess, z } from "zod";
import { zfd } from "zod-form-data";
import type { RequestParams } from "~/api/client";
import { apiClient } from "~/api/client";
import {
  DEFAULT_LOGS_PER_PAGE,
  DEFAULT_QUERY_REFETCH_INTERVAL,
  LOGS_QUERY_REFETCH_INTERVAL,
  METRICS_TIME_RANGES
} from "~/lib/constants";
import {
  type DeploymentLogQueryData,
  type HTTPLogFilters,
  type HttpLogQueryData,
  LOG_LEVELS
} from "~/lib/queries/logs";
import { projectQueries } from "~/lib/queries/projects";
import type { Writeable } from "~/lib/types";
import { notFound } from "~/lib/utils";

/************************************
 *       Compose Stack Queries      *
 ************************************/

export const stackDeploymentListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional(),
  status: zfd.repeatable(
    z
      .array(z.enum(["QUEUED", "DEPLOYING", "FINISHED", "FAILED", "CANCELLED"]))
      .optional()
      .catch(undefined)
  ),
  queued_at_before: z.coerce.date().optional().catch(undefined),
  queued_at_after: z.coerce.date().optional().catch(undefined)
});

export type StackDeploymentListFilters = z.infer<
  typeof stackDeploymentListFilters
>;

export const stackMetrisSearch = z.object({
  time_range: z
    .enum(METRICS_TIME_RANGES)
    .optional()
    .default("LAST_HOUR")
    .catch("LAST_HOUR"),
  service_names: zfd.repeatable(z.array(z.string()))
});

export type StackMetricsFilters = z.TypeOf<typeof stackMetrisSearch>;

export const stackRuntimeLogSearchSchema = zfd.formData({
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
  container_id: z.string().optional(),
  isMaximized: preprocess(
    (arg) => arg === "true",
    z.coerce.boolean().optional().catch(false)
  ),
  context: z.coerce.number().optional().catch(undefined),
  context_lines: z.coerce.number().min(5).optional().catch(undefined)
});

export type ComposeStackRuntimeLogFilters = z.infer<
  typeof stackRuntimeLogSearchSchema
>;

export const composeStackQueries = {
  single: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug
  }: {
    workspaceId: string;
    project_slug: string;
    env_slug: string;
    stack_slug: string;
  }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(workspaceId, project_slug).queryKey,
        env_slug,
        "COMPOSE_STACK_DETAILS",
        stack_slug
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/",
          {
            params: {
              path: {
                project_slug,
                slug: stack_slug,
                env_slug
              }
            },
            signal
          }
        );

        if (!data) {
          throw notFound(
            `The compose stack \`${stack_slug}\` doesn't exist in this project.`
          );
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      },
      refetchIntervalInBackground: true
    }),
  singleDeployment: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    deployment_hash
  }: {
    workspaceId: string;
    project_slug: string;
    env_slug: string;
    stack_slug: string;
    deployment_hash: string;
  }) =>
    queryOptions({
      queryKey: [
        ...composeStackQueries.deploymentList({
          workspaceId,
          project_slug,
          env_slug,
          stack_slug
        }).queryKey,
        "DETAILS",
        deployment_hash
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deployments/{hash}/",
          {
            params: {
              path: {
                project_slug,
                slug: stack_slug,
                env_slug,
                hash: deployment_hash
              }
            },
            signal
          }
        );

        if (!data) {
          throw notFound(
            `The Deployment \`${stack_slug}\` doesn't exist in this stack.`
          );
        }
        return data;
      },
      refetchInterval: (query) => {
        if (query.state.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      },
      refetchIntervalInBackground: true
    }),
  deploymentLogs: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    deployment_hash,
    queryClient,
    autoRefetchEnabled
  }: {
    workspaceId: string;
    project_slug: string;
    env_slug: string;
    stack_slug: string;
    deployment_hash: string;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...composeStackQueries.singleDeployment({
          workspaceId,
          project_slug,
          stack_slug,
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
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deployments/{hash}/build-logs/",
          {
            params: {
              path: {
                project_slug,
                slug: stack_slug,
                env_slug,
                hash: deployment_hash
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
  deploymentList: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    filters = {}
  }: {
    workspaceId: string;
    project_slug: string;
    env_slug: string;
    stack_slug: string;
    filters?: StackDeploymentListFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          env_slug,
          stack_slug
        }).queryKey,
        "DEPLOYMENT_LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deployments/",
          {
            params: {
              path: {
                project_slug,
                slug: stack_slug,
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
          throw notFound(
            `The compose stack \`${stack_slug}\` doesn't exist in this project.`
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
  httpLogs: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    stack_id,
    queryClient,
    stack_service_name,
    autoRefetchEnabled = true,
    filters = {}
  }: {
    workspaceId: string;
    stack_id: string;
    project_slug: string;
    stack_slug: string;
    env_slug: string;
    filters?: Omit<HTTPLogFilters, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
    stack_service_name?: string[];
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          stack_slug,
          env_slug
        }).queryKey,
        "HTTP_LOGS",
        stack_id,
        stack_service_name,
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
              stack_id,
              stack_service_name:
                (stack_service_name ?? []).length === 0
                  ? undefined
                  : stack_service_name,
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
                stack_id,
                stack_service_name:
                  (stack_service_name ?? []).length === 0
                    ? undefined
                    : stack_service_name,
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
  singleHttpLog: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    request_uuid
  }: {
    workspaceId: string;
    project_slug: string;
    stack_slug: string;
    env_slug: string;
    request_uuid: string;
  }) =>
    queryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          stack_slug,
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
    env_slug,
    stack_id,
    stack_slug,
    field,
    value
  }: {
    workspaceId: string;
    project_slug: string;
    stack_id: string;
    stack_slug: string;
    env_slug: string;
    field: RequestParams<"get", "/api/http-logs/fields/">["field"];
    value: string;
  }) =>
    queryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          stack_slug,
          env_slug
        }).queryKey,
        stack_id,
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
              stack_id
            }
          }
        });
        return data ?? [];
      }
    }),
  metrics: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    filters
  }: {
    workspaceId: string;
    project_slug: string;
    stack_slug: string;
    env_slug: string;
    filters?: StackMetricsFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          stack_slug,
          env_slug
        }).queryKey,
        "METRICS",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/metrics/",
          {
            params: {
              path: {
                project_slug,
                slug: stack_slug,
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
  runtimeLogs: ({
    workspaceId,
    project_slug,
    service_name,
    stack_slug,
    env_slug,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    workspaceId: string;
    project_slug: string;
    service_name: string;
    stack_slug: string;
    env_slug: string;
    filters?: Omit<ComposeStackRuntimeLogFilters, "isMaximized">;
    queryClient: QueryClient;
    autoRefetchEnabled?: boolean;
  }) =>
    infiniteQueryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          stack_slug,
          env_slug
        }).queryKey,
        "RUNTIME_LOGS",
        service_name,
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
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/runtime-logs/",
          {
            params: {
              path: {
                project_slug,
                env_slug,
                slug: stack_slug
              },
              query: {
                stack_service_name: service_name,
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
  logWithContext: ({
    workspaceId,
    project_slug,
    stack_slug,
    env_slug,
    service_name,
    time,
    context_lines = 20
  }: {
    workspaceId: string;
    project_slug: string;
    service_name: string;
    stack_slug: string;
    env_slug: string;
    time: number;
    context_lines?: number;
  }) =>
    queryOptions({
      queryKey: [
        ...composeStackQueries.single({
          workspaceId,
          project_slug,
          stack_slug,
          env_slug
        }).queryKey,
        "RUNTIME_LOGS",
        "WITH_CONTEXT",
        time,
        context_lines
      ],
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/runtime-logs/with-context/{time}/",
          {
            params: {
              path: {
                project_slug,
                slug: stack_slug,
                env_slug,
                time: time.toString()
              },
              query: {
                lines: context_lines,
                stack_service_name: service_name
              }
            },
            signal
          }
        );

        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return LOGS_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
    })
};
