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
  DEFAULT_QUERY_REFETCH_INTERVAL
} from "~/lib/constants";
import type {
  HTTPLogFilters,
  HttpLogQueryData,
  paginationListFilters
} from "~/lib/queries/shared";
import { durationToMs, notFound } from "~/lib/utils";

export const buildRegistryImageListFilters = zfd.formData({
  cursor: z.string().optional().catch(undefined)
});

export const buildRegistryQueries = {
  list: (filters: z.infer<typeof paginationListFilters>) =>
    queryOptions({
      queryKey: ["BUILD_REGISTRY_CREDENTIALS", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/registries/build-registries/",
          {
            signal,
            params: {
              query: filters
            }
          }
        );
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
      queryKey: ["BUILD_REGISTRY_CREDENTIALS", id] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/registries/build-registries/{id}/",
          {
            signal,
            params: {
              path: {
                id
              }
            }
          }
        );
        if (!data) {
          throw notFound(
            `No build registry credentials found with the ID ${id}`
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
  imageList: (
    id: string,
    params: z.infer<typeof buildRegistryImageListFilters>
  ) =>
    queryOptions({
      queryKey: [
        ...buildRegistryQueries.single(id).queryKey,
        "IMAGE_LIST",
        params
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/registries/build-registries/{id}/list-images/",
          {
            params: {
              path: {
                id
              },
              query: params
            },
            signal
          }
        );

        if (!data) throw new Error("Not found");
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
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

export const passwordTokenListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional()
});

export const passwordTokenQueries = {
  list: (filters: z.infer<typeof passwordTokenListFilters> = {}) =>
    queryOptions({
      queryKey: ["PASSWORD_RESET_TOKENS", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/console/password-tokens/", {
          signal,
          params: {
            query: filters
          }
        });
        if (!data) throw notFound("Not found");
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
    })
};

export const serverUserListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional(),
  query: z.string().optional(),
  is_active: z
    .preprocess(
      (arg) => arg === "true",
      z.coerce.boolean().optional().catch(undefined)
    )
    .optional()
});

export const serverUserQueries = {
  list: (filters: z.infer<typeof serverUserListFilters> = {}) =>
    queryOptions({
      queryKey: ["SERVER_USERS", "LIST", filters] as const,
      queryFn: async ({ signal }) => {
        console.log({ filters });
        const { data } = await apiClient.GET("/api/console/users/", {
          signal,
          params: {
            query: filters
          }
        });
        if (!data) throw notFound("Not found");
        return data;
      },
      refetchInterval: (query) => {
        if (!query.state.data) {
          return false;
        }
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      },
      placeholderData: keepPreviousData
    })
};

export const adminWorkspaceQueries = {
  list: (filters: z.infer<typeof paginationListFilters>) =>
    queryOptions({
      queryKey: ["SERVER_WORKSPACES", "LIST", filters] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/console/workspaces/", {
          signal,
          params: {
            query: filters
          }
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
      queryKey: ["SERVER_WORKSPACES", "SINGLE", id] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/console/workspaces/{id}/", {
          signal,
          params: {
            path: { id }
          }
        });
        if (!data) {
          throw notFound(`Workspace with id \`${id}\` not found !`);
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

export const proxyHttpLogQueries = {
  list: ({
    filters = {},
    source,
    autoRefetchEnabled = true,
    queryClient
  }: {
    filters?: Omit<HTTPLogFilters, "isMaximized">;
    source?: string[];
    autoRefetchEnabled?: boolean;
    queryClient: QueryClient;
  }) =>
    infiniteQueryOptions({
      queryKey: ["PROXY_HTTP_LOGS", filters, source] as const,
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

        const { data } = await apiClient.GET("/api/console/proxy/http-logs/", {
          params: {
            query: {
              ...filters,
              source,
              cursor,
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
          const { data: nextPage } = await apiClient.GET(
            "/api/console/proxy/http-logs/",
            {
              params: {
                query: {
                  ...filters,
                  source,
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
  single: (request_uuid: string) =>
    queryOptions({
      queryKey: ["PROXY_HTTP_LOGS", request_uuid] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/console/proxy/http-logs/{request_uuid}/",
          {
            params: {
              path: {
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
    field,
    value
  }: {
    field: RequestParams<
      "get",
      "/api/console/proxy/http-logs/fields/"
    >["field"];
    value: string;
  }) =>
    queryOptions({
      queryKey: ["PROXY_HTTP_LOGS", "FIELDS", field, value] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/console/proxy/http-logs/fields/",
          {
            signal,
            params: {
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

export const licenseQueries = {
  get: queryOptions({
    queryKey: ["LICENSE"],
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/license/details/", { signal });
      return data ?? null;
    },
    refetchInterval: (query) => {
      if (query.state.data) {
        return durationToMs(30, "minutes");
      }
      return false;
    }
  })
};

export const systemQueries = {
  settings: queryOptions({
    queryKey: ["SYSTEM_SETTINGS"],
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET("/api/console/system-settings/", {
        signal
      });
      if (!data) {
        throw notFound(`Oops`);
      }
      return data;
    },
    refetchInterval: (query) => {
      if (query.state.data) {
        return durationToMs(30, "minutes");
      }
      return false;
    }
  })
};
