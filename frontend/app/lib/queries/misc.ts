import { queryOptions } from "@tanstack/react-query";
import { z } from "zod";
import { zfd } from "zod-form-data";
import { apiClient } from "~/api/client";
import type {
  TemplateDetailsApiResponse,
  TemplateSearchAPIResponse
} from "~/api/types";
import { TEMPLATE_API_HOST } from "~/lib/constants";
import { durationToMs, notFound } from "~/lib/utils";
import { workspaceKey } from "./shared";

export const serverQueries = {
  settings: queryOptions({
    queryKey: ["APP_SETTINGS"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/settings/");
      return data ?? null;
    },
    staleTime: Number.MAX_SAFE_INTEGER
  }),
  resourceLimits: queryOptions({
    queryKey: ["SERVICE_RESOURCE_LIMITS"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/server/resource-limits/");
      if (!data) throw new Error("Unknown error with the API");
      return data;
    },
    staleTime: Number.MAX_SAFE_INTEGER
  }),
  ongoingUpdate: queryOptions({
    queryKey: ["ONGOING_UPDATE"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/check-ongoing-update-status/");
      if (!data) throw new Error("Unknown error with the API");
      return data;
    }
  })
};

export type LatestRelease = {
  tag: string;
  url: string;
  body: string;
};

export const versionQueries = {
  latest: queryOptions<LatestRelease | null>({
    queryKey: ["LATEST_RELEASE"] as const,
    queryFn: async ({ signal }) => {
      try {
        const response = await fetch(
          "https://cdn.zaneops.dev/api/latest-release",
          { signal }
        );
        return response.json() as Promise<LatestRelease>;
      } catch (error) {
        return null;
      }
    },
    refetchInterval: durationToMs(1, "hours")
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

/************************************
 *       Stack Template Queries     *
 ************************************/

export const templateSearchFilters = zfd.formData({
  query: z.string().optional().catch(""),
  page: zfd.numeric().catch(1).optional().default(1),
  perPage: zfd.numeric().optional().catch(15).optional().default(15),
  tags: zfd.repeatable(z.array(z.string())).optional().default([])
});

export type TemplateSearchFilters = z.infer<typeof templateSearchFilters>;

export const templateQueries = {
  search: (filters: TemplateSearchFilters) =>
    queryOptions({
      queryKey: ["TEMPLATE_SEARCH", filters],
      queryFn: async ({ signal }) => {
        const url = new URL("/api/search", TEMPLATE_API_HOST);

        if (filters.query) {
          url.searchParams.set("q", filters.query);
        }

        if (filters.page) {
          url.searchParams.set("page", filters.page.toString());
        }

        if (filters.perPage) {
          url.searchParams.set("per_page", filters.perPage.toString());
        }

        for (const tag of filters.tags) {
          url.searchParams.append("tags", tag);
        }

        const response = await fetch(url, { signal });

        if (!response.ok) {
          throw new Error("Failed to fetch templates");
        }

        return response.json() as Promise<TemplateSearchAPIResponse>;
      }
    }),
  tags: queryOptions({
    queryKey: ["TEMPLATE_SEARCH", "TAGS"],
    queryFn: async ({ signal }) => {
      const url = new URL("/api/tags.json", TEMPLATE_API_HOST);
      const response = await fetch(url, { signal });

      if (!response.ok) {
        throw new Error("Failed to fetch tags");
      }

      return response.json() as Promise<string[]>;
    }
  }),
  single: (templateSlug: string) =>
    queryOptions({
      queryKey: ["TEMPLATE_SEARCH", templateSlug],
      queryFn: async ({ signal }) => {
        const url = new URL(
          `/api/templates/${templateSlug}.json`,
          TEMPLATE_API_HOST
        );
        const response = await fetch(url, { signal });

        if (!response.ok) {
          throw notFound("This template doesn't exist on ZaneOps");
        }

        return response.json() as Promise<TemplateDetailsApiResponse>;
      }
    })
};
