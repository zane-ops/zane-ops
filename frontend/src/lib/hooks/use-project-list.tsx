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
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return TEN_SECONDS;
      }
      return false;
    },
  });
}

export function useArchivedProject() {
  return useQuery({
    queryKey: projectKeys.archived,
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/archived-projects/", {
        signal,
      });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return TEN_SECONDS;
      }
      return false;
    },
  });
}
