import { queryOptions } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { durationToMs } from "~/lib/utils";

export const serverQueries = {
  settings: queryOptions({
    queryKey: ["APP_SETTINGS"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/settings/");
      // we throw the error because we want ZaneOps to retry this for multiple times at least
      return data;
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
