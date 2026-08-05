import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import { workspaceKey } from "~/lib/queries/shared";
import { durationToMs, notFound } from "~/lib/utils";

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
