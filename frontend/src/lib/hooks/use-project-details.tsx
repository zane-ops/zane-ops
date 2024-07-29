import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { type ProjectDetailsSearch, projectKeys } from "~/key-factories";

const TEN_SECONDS = 10 * 1000;

export function useProjectDetails(slug: string, filters: ProjectDetailsSearch) {
  return useQuery({
    queryKey: projectKeys.detail(slug, filters),
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
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      if (query.state.data?.data) {
        return TEN_SECONDS;
      }
      return false;
    }
  });
}
