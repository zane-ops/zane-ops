import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { serviceKeys } from "~/key-factories";
import { DEFAULT_QUERY_REFETCH_INTERVAL } from "~/lib/constants";

export function useDockerServiceSingleQuery(
  project_slug: string,
  service_slug: string
) {
  return useQuery({
    queryKey: serviceKeys.single(project_slug, service_slug, "docker"),
    queryFn: ({ signal }) => {
      return apiClient.GET(
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
    },
    refetchInterval: (query) => {
      if (query.state.data?.data) {
        return DEFAULT_QUERY_REFETCH_INTERVAL;
      }
      return false;
    }
  });
}

export type DockerService = Exclude<
  Exclude<
    ReturnType<typeof useDockerServiceSingleQuery>["data"],
    undefined
  >["data"],
  undefined
>;
