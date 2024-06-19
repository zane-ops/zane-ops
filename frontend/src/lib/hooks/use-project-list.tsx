import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { projectKeys } from "~/key-factories";

const TEN_SECONDS = 10 * 1000;

export function useProjectList(filters: {
  sort_by?: ("slug" | "-slug" | "updated_at" | "-updated_at")[];
  slug?: string;
  page?: number;
  per_page?: number;
}) {
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
