import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { serviceKeys } from "~/key-factories";
import { getCsrfTokenHeader } from "~/utils";

export function useRedeployDockerServiceMutation(
  project_slug: string,
  service_slug: string,
  deployment_hash: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const { error, data } = await apiClient.PUT(
        "/api/projects/{project_slug}/deploy-service/docker/{service_slug}/{deployment_hash}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              service_slug,
              deployment_hash
            }
          }
        }
      );

      if (error) return error;
      if (data) {
        await queryClient.invalidateQueries({
          queryKey: serviceKeys.single(project_slug, service_slug, "docker"),
          exact: false
        });
        return;
      }
    }
  });
}
