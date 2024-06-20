import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { type ProjectSearch, projectKeys } from "~/key-factories";

const TEN_SECONDS = 10 * 1000;

export function useProjectList(filters: ProjectSearch) {
  return useQuery({
    queryKey: projectKeys.list(filters),
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/", {
        params: {
          query: filters,
        },
        signal,
      });
    },
    placeholderData: keepPreviousData,
    enabled: filters.status !== "archived",
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return TEN_SECONDS;
      }
      return false;
    },
  });
}

export function useArchivedProjectList(filters: ProjectSearch) {
  return useQuery({
    queryKey: projectKeys.archived(filters),
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/archived-projects/", {
        param: {
          query: filters,
        },
        signal,
      });
    },
    enabled: filters.status === "archived",
  });
}
