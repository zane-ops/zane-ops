import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { type ProjectSearch, projectKeys } from "~/key-factories";

const FIVE_SECONDS = 5 * 1000;

export function useProjectList(filters: ProjectSearch) {
  return useQuery({
    queryKey: projectKeys.list(filters),
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
    placeholderData: keepPreviousData,
    enabled: filters.status !== "archived",
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return FIVE_SECONDS;
      }
      return false;
    }
  });
}

export function useArchivedProjectList(filters: ProjectSearch) {
  return useQuery({
    queryKey: projectKeys.archived(filters),
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
    placeholderData: keepPreviousData,
    enabled: filters.status === "archived"
  });
}
