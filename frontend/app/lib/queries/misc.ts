import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { workspaceKey } from "./shared";

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

export const resourceQueries = {
  search: (workspaceId: string, query?: string) =>
    queryOptions({
      queryKey: [...workspaceKey(workspaceId), "RESOURCES", query] as const,
      queryFn: async ({ signal }) => {
        return apiClient.GET("/api/search-resources/", {
          params: {
            query: {
              query: (query ?? "").trim()
            }
          },
          signal
        });
      }
    })
};
