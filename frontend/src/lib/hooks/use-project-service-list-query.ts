import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { type ProjectServiceListSearch, projectKeys } from "~/key-factories";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";

export function useProjectServiceListQuery(
  slug: string,
  filters: ProjectServiceListSearch
) {
  return useQuery({
    queryKey: projectKeys.serviceList(slug, filters),
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
  });
}
