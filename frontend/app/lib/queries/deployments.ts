import {
  type InfiniteData,
  type QueryClient,
  infiniteQueryOptions,
  keepPreviousData,
  queryOptions,
  type skipToken
} from "@tanstack/react-query";
import type { RequestParams } from "~/api/client";
import { apiClient } from "~/api/client";
import {
  DEFAULT_LOGS_PER_PAGE,
  DEFAULT_QUERY_REFETCH_INTERVAL,
  LOGS_QUERY_REFETCH_INTERVAL
} from "~/lib/constants";
import type {
  DeploymentLogFilters,
  DeploymentLogQueryData,
  HTTPLogFilters,
  HttpLogQueryData
} from "~/lib/queries/logs";
import { projectQueries } from "~/lib/queries/projects";
import type { MetricsFilters } from "~/lib/queries/services";
import { workspaceKey } from "~/lib/queries/shared";
import { notFound } from "~/lib/utils";

export const deploymentQueries = {
  recent: (workspaceId: string) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "RECENT_DEPLOYMENTS"] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/recent-deployments/", {
          signal
        });
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
  single: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    deployment_hash
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
  }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(workspaceId, project_slug).queryKey,
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
      },
      refetchIntervalInBackground: true
    }),
  logs: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    workspaceId: string;
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
          workspaceId,
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
  logWithContext: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    time,
    context_lines = 20
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    time: number;
    context_lines?: number;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
        }).queryKey,
        "RUNTIME_LOGS",
        "WITH_CONTEXT",
        time,
        context_lines
      ],
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/deployments/{deployment_hash}/runtime-logs/with-context/{time}",
          {
            params: {
              path: {
                project_slug,
                service_slug,
                env_slug,
                deployment_hash,
                time: time.toString()
              },
              query: {
                lines: context_lines
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
    }),
  buildLogs: ({
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    queryClient
  }: {
    workspaceId: string;
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
          workspaceId,
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
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    filters
  }: {
    workspaceId: string;
    project_slug: string;
    deployment_hash: string;
    service_slug: string;
    env_slug: string;
    filters?: MetricsFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          workspaceId,
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
    workspaceId,
    project_slug,
    service_slug,
    env_slug,
    deployment_hash,
    autoRefetchEnabled = true,
    filters = {},
    queryClient
  }: {
    workspaceId: string;
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
          workspaceId,
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
              deployment_id: deployment_hash,
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
                per_page: DEFAULT_LOGS_PER_PAGE,
                deployment_id: deployment_hash,
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
    service_slug,
    env_slug,
    deployment_hash,
    request_uuid
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    request_uuid: string;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          workspaceId,
          project_slug,
          service_slug,
          env_slug,
          deployment_hash
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
    deployment_hash,
    field,
    value
  }: {
    workspaceId: string;
    project_slug: string;
    service_slug: string;
    env_slug: string;
    deployment_hash: string;
    field: RequestParams<"get", "/api/http-logs/fields/">["field"];
    value: string;
  }) =>
    queryOptions({
      queryKey: [
        ...deploymentQueries.single({
          workspaceId,
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
        const { data } = await apiClient.GET("/api/http-logs/fields/", {
          signal,
          params: {
            query: {
              field,
              value,
              deployment_hash
            }
          }
        });
        return data ?? [];
      }
    })
};
