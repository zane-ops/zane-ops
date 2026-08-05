import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { apiClient } from "~/api/client";
import {
  DEFAULT_QUERY_REFETCH_INTERVAL,
  WORKSPACE_ROLE_MAPPING
} from "~/lib/constants";
import { durationToMs, notFound } from "~/lib/utils";
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

export const gitAppsQueries = {
  list: (workspaceId: string) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "GIT_APPS"] as const,
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
  single: (workspaceId: string, id: string) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "GIT_APPS", id] as const,
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
  github: (workspaceId: string, id: string) =>
    queryOptions({
      queryKey: [
        ...gitAppsQueries.list(workspaceId).queryKey,
        "GITHUB",
        id
      ] as const,
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
  gitlab: (workspaceId: string, id: string) =>
    queryOptions({
      queryKey: [
        ...gitAppsQueries.list(workspaceId).queryKey,
        "GITLAB",
        id
      ] as const,
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
  repositoryBranches: (
    workspaceId: string,
    repoUrl: string,
    gitAppId?: string
  ) =>
    queryOptions({
      queryKey: [
        ...workspaceKey(workspaceId),
        "GIT_REPOSITORY_BRANCHES",
        repoUrl
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/connectors/repository-branches/",
          {
            params: {
              query: {
                repository_url: repoUrl,
                git_app_id: gitAppId
              }
            },
            signal
          }
        );
        return data ?? [];
      },
      enabled: () => z.string().url().safeParse(repoUrl).success, // only filter URLs to prevent errors when making requests in the backend
      staleTime: durationToMs(30, "seconds"),
      placeholderData: keepPreviousData
    }),
  repositories: (
    workspaceId: string,
    id: string,
    filters: { query?: string } = {}
  ) =>
    queryOptions({
      queryKey: [
        ...gitAppsQueries.single(workspaceId, id).queryKey,
        "REPOSITORIES",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/connectors/{id}/repositories/",
          {
            params: {
              path: {
                id
              },
              query: {
                // do not pass `filters.query` if empty
                query: filters.query?.trim() ? filters.query.trim() : undefined
              }
            },
            signal
          }
        );

        if (!data) {
          throw notFound("Oops !");
        }

        return data;
      },
      placeholderData: keepPreviousData
    })
};

export const serverUserListFilters = zfd.formData({
  page: zfd.numeric().optional().catch(1).optional(),
  per_page: zfd.numeric().optional().catch(10).optional(),
  query: z.string().optional()
});

export const serverUserQueries = {
  list: (filters: z.infer<typeof serverUserListFilters> = {}) =>
    queryOptions({
      queryKey: ["SERVER_USERS", filters] as const,
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
