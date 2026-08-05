import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import { notFound } from "~/lib/utils";
import { workspaceKey } from "./shared";

export const sharedRegistryCredentialsQueries = {
  list: (workspaceId: string) =>
    queryOptions({
      queryKey: [
        ...workspaceKey(workspaceId),
        "SHARED_REGISTRY_CREDENTIALS"
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET("/api/registries/credentials/", {
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
  single: (workspaceId: string, id: string) =>
    queryOptions({
      queryKey: [
        ...workspaceKey(workspaceId),
        "SHARED_REGISTRY_CREDENTIALS",
        id
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/registries/credentials/{id}/",
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
            `No container registry credentials found with the ID ${id}`
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
    })
};
export const buildRegistryListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional()
});

export const buildRegistryImageListFilters = zfd.formData({
  cursor: z.string().optional().catch(undefined)
});

export const buildRegistryQueries = {
  list: (filters: z.infer<typeof buildRegistryListFilters>) =>
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
