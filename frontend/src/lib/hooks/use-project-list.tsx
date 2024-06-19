import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { projectKeys } from "~/key-factories";

const TEN_SECONDS = 10 * 1000;

export function useProjectList(filters: {
  slug?: string;
  page?: number;
  per_page?: number;
}) {
  return useQuery({
    queryKey: projectKeys.list({
      slug: filters.slug,
      page: filters.page,
      per_page: filters.per_page
    }),
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/", {
        params: {
          query: {
            slug: filters.slug,
            per_page: filters.per_page,
            page: filters.page
          }
        },
        signal
      });
    },
    placeholderData: keepPreviousData,
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return TEN_SECONDS;
      }
      return false;
    }
  });
}
