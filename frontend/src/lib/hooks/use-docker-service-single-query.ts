import { useQuery } from "@tanstack/react-query";
import { type ApiResponse, apiClient } from "~/api/client";
import { serviceKeys } from "~/key-factories";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";

export function useDockerServiceSingleQuery({
  project_slug,
  service_slug
}: {
  project_slug: string;
  service_slug: string;
}) {
  return useQuery({
    queryKey: serviceKeys.single(project_slug, service_slug, "docker"),
    queryFn: async ({ signal }) => {
      const { data } = await apiClient.GET(
        "/api/projects/{project_slug}/service-details/docker/{service_slug}/",
        {
          params: {
            path: {
              project_slug,
              service_slug
            }
          },
          signal
        }
      );
      return data;
    },
    refetchInterval: (query) => {
      if (query.state.data) {
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      }
      return false;
    }
  });
}

export type DockerService = ApiResponse<
  "get",
  "/api/projects/{project_slug}/service-details/docker/{service_slug}/"
>;
