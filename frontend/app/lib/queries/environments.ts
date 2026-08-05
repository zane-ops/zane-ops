import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";
import { notFound } from "~/lib/utils";
import { type ProjectSearch, projectQueries } from "./projects";
import type { ProjectServiceListSearch } from "./services";

export const environmentQueries = {
  single: (workspaceId: string, project_slug: string, env_slug: string) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(workspaceId, project_slug).queryKey,
        env_slug
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{slug}/environment-details/{env_slug}/",
          {
            params: {
              path: {
                slug: project_slug,
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

  serviceList: (
    workspaceId: string,
    project_slug: string,
    env_slug: string,
    filters: ProjectServiceListSearch = {}
  ) =>
    queryOptions({
      queryKey: [
        ...environmentQueries.single(workspaceId, project_slug, env_slug)
          .queryKey,
        "SERVICE_LIST",
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
                slug: project_slug,
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

  composeStackList: (
    workspaceId: string,
    project_slug: string,
    env_slug: string,
    filters: ProjectSearch = {}
  ) =>
    queryOptions({
      queryKey: [
        ...environmentQueries.single(workspaceId, project_slug, env_slug)
          .queryKey,
        "COMPOSE_STACK_LIST",
        filters
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/compose/stacks/{project_slug}/{env_slug}/",
          {
            params: {
              query: {
                ...filters
              },
              path: {
                project_slug,
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

  pendingReview: (
    workspaceId: string,
    project_slug: string,
    env_slug: string
  ) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(workspaceId, project_slug).queryKey,
        env_slug,
        "PENDING_REVIEW"
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{slug}/environment-details/{env_slug}/review-preview-deployment/",
          {
            params: {
              path: {
                slug: project_slug,
                env_slug
              }
            },
            signal
          }
        );
        if (!data) {
          throw notFound(
            `No pending environment to review exists at \`${project_slug}/${env_slug}\` `
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
