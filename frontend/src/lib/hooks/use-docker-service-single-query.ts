import { useQuery } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { serviceKeys } from "~/key-factories";

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
    }
  });
}
