import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import type { paginationListFilters } from "~/lib/queries/shared";
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
  is_active: z.preprocess(
    (arg) => arg === "true",
    z.coerce.boolean().optional().catch(false)
  )
});

export const serverUserQueries = {
  list: (filters: z.infer<typeof serverUserListFilters> = {}) =>
    queryOptions({
      queryKey: ["SERVER_USERS", "LIST", filters] as const,
      queryFn: async ({ signal }) => {
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
