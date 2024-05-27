import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";

const TWO_MINUTES = 2 * 60 * 1000;

export function useProjectList() {
  return useQuery({
    queryKey: ["PROJECT_LIST"],
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/", { signal });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return TWO_MINUTES;
      }
      return false;
    }
  });
}
