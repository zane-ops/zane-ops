import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { type ProjectSearch, projectKeys } from "~/key-factories";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";

export function useProjectListQuery(filters: ProjectSearch) {
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
    enabled: filters.status !== "archived",
    refetchInterval: (query) => {
      if (query.state.data?.data) {
        return DEFAULT_QUERY_REFETCH_INTERVAL;
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
    enabled: filters.status === "archived"
  });
}
