import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { dockerHubKeys } from "~/key-factories";

export function useSearchDockerHubQuery(query: string) {
  return useQuery({
    queryKey: dockerHubKeys.images(query.trim()),
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/docker/image-search/", {
        params: {
          query: {
            q: query.trim()
          }
        },
        signal
      });
    },
    enabled: query.trim().length > 0
  });
}
