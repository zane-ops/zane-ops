import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { projectKeys } from "~/key-factories";

export function useProjectSingle(slug: string) {
  return useQuery({
    queryKey: projectKeys.single(slug),
    queryFn: ({ signal }) => {
      return apiClient.GET("/api/projects/{slug}/", {
        params: {
          path: {
            slug
          }
        },
        signal
      });
    },
    placeholderData: keepPreviousData
  });
}
