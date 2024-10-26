import { keepPreviousData, queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { type ApiResponse, apiClient } from "~/api/client";
import {
  DEFAULT_QUERY_REFETCH_INTERVAL,
  DEPLOYMENT_STATUSES
} from "~/lib/constants";
import type { Writeable } from "~/lib/types";

const THIRTY_MINUTES = 30 * 60 * 1000; // in milliseconds

export const userQueries = {
  authedUser: queryOptions({
    queryKey: ["AUTHED_USER"] as const,
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/auth/me/", { signal });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.user) {
        return THIRTY_MINUTES;
      }
      return false;
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

export const projectSearchSchema = z.object({
  slug: z.string().optional().catch(""),
  page: z.number().optional().catch(1),
  per_page: z.number().optional().catch(10),
  sort_by: z
    .array(
      z.enum([
        "slug",
        "-slug",
        "updated_at",
        "-updated_at",
        "archived_at",
        "-archived_at"
      ])
    )
    .optional()
    .catch(["-updated_at"]),
  status: z.enum(["active", "archived"]).optional().catch("active")
});

export type ProjectSearch = z.infer<typeof projectSearchSchema>;

export const projectQueries = {
  list: (filters: ProjectSearch = {}) =>
    queryOptions({
      queryKey: ["PROJECT_LIST", filters] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/projects/", {
          params: {
            query: {
              ...filters,
              sort_by: filters.sort_by?.filter(
                (criteria) =>
                  criteria !== "-archived_at" && criteria !== "archived_at"
              )
            }
          },
          signal
        });
      },
      enabled: filters.status !== "archived",
      refetchInterval: (query) => {
        if (query.state.data?.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    }),
  archived: (filters: ProjectSearch) =>
    queryOptions({
      queryKey: ["ARCHIVED_PROJECT_LIST", filters] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/archived-projects/", {
          params: {
            query: {
              ...filters,
              sort_by: filters.sort_by?.filter(
                (criteria) =>
                  criteria !== "-updated_at" && criteria !== "updated_at"
              )
            }
          },
          signal
        });
      },
      enabled: filters.status === "archived"
    }),
  single: (slug: string) =>
    queryOptions({
      queryKey: ["PROJECT_SINGLE", slug] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/projects/{slug}/", {
          params: {
            path: {
              slug
            }
          },
          signal
        });
      },
      placeholderData: keepPreviousData
    }),
  serviceList: (slug: string, filters: ProjectServiceListSearch) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(slug).queryKey,
        "SERVICE-LIST",
        filters
      ] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET("/api/projects/{slug}/service-list/", {
          params: {
            query: {
              ...filters
            },
            path: {
              slug
            }
          },
          signal
        });
      },
      refetchInterval: (query) => {
        if (query.state.data?.data) {
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

export const serviceDeploymentListFilters = z.object({
  page: z.number().optional().catch(1).optional(),
  per_page: z.number().optional().catch(10).optional(),
  status: z
    .array(z.enum(DEPLOYMENT_STATUSES))
    .optional()
    .catch(DEPLOYMENT_STATUSES as Writeable<typeof DEPLOYMENT_STATUSES>),
  queued_at_before: z.coerce.date().optional().catch(undefined),
  queued_at_after: z.coerce.date().optional().catch(undefined)
});

export type ServiceDeploymentListFilters = z.infer<
  typeof serviceDeploymentListFilters
>;

export type DockerService = ApiResponse<
  "get",
  "/api/projects/{project_slug}/service-details/docker/{service_slug}/"
>;

export const serviceQueries = {
  single: ({
    project_slug,
    service_slug,
    type = "docker"
  }: { project_slug: string; service_slug: string; type?: "docker" | "git" }) =>
    queryOptions({
      queryKey: [
        ...projectQueries.single(project_slug).queryKey,
        "SERVICE_DETAILS",
        type,
        service_slug
      ] as const,
      queryFn: async ({ signal }) => {
        const { data } = await apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/",
          {
            params: {
              path: {
                project_slug,
                service_slug
              }
            },
            signal
          }
        );
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
    type = "docker",
    filters = {}
  }: {
    project_slug: string;
    service_slug: string;
    type?: "docker" | "git";
    filters?: ServiceDeploymentListFilters;
  }) =>
    queryOptions({
      queryKey: [
        ...serviceQueries.single({ project_slug, service_slug, type }).queryKey,
        "DEPLOYMENT_LIST",
        filters
      ] as const,
      queryFn: ({ signal }) => {
        return apiClient.GET(
          "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/",
          {
            params: {
              path: {
                project_slug,
                service_slug
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
      },
      refetchInterval: (query) => {
        if (query.state.data?.data) {
          return DEFAULT_QUERY_REFETCH_INTERVAL;
        }
        return false;
      }
    })
};
