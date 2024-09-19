import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import {
  type ServiceDeploymentListFilters,
  serviceKeys
} from "~/key-factories";

const FIVE_SECONDS = 5 * 1000;

export function useDockerServiceDeploymentListQuery(
  project_slug: string,
  service_slug: string,
  filters: ServiceDeploymentListFilters
) {
  return useQuery({
    queryKey: serviceKeys.deploymentList(
      project_slug,
      service_slug,
      "docker",
      filters
    ),
    queryFn: ({ signal }) => {
      return apiClient.GET(
        "/api/projects/{project_slug}/service-details/docker/{service_slug}/deployments/",
        {
          params: {
            path: {
              project_slug,
              service_slug
            },
            query: {
              ...filters,
              queued_at_after: filters.queued_at_after?.toISOString(),
              queued_at_before: filters.queued_at_before?.toISOString()
            }
          },
          signal
        }
      );
    },
    refetchInterval: (query) => {
      if (query.state.data?.data) {
        return FIVE_SECONDS;
      }
      return false;
    }
  });
}
