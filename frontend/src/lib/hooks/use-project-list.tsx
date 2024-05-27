import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { projectKeys } from "~/key-factories";

const TEN_SECONDS = 10 * 1000;

export function useProjectList() {
  return useQuery({
    queryKey: projectKeys.list,
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/", { signal });
    },
    refetchInterval: (query) => {
      if (query.state.data?.data?.results) {
        return TEN_SECONDS;
      }
      return false;
    },
  });
}
