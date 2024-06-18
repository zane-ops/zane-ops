import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { projectKeys } from "~/key-factories";

const TEN_SECONDS = 10 * 1000;

export function useProjectList(filters: { slug?: string }) {
  return useQuery({
    queryKey: projectKeys.list({ slug: filters.slug }),
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/", {
        params: {
          query: {
            slug: filters.slug,
          },
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
