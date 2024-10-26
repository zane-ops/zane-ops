import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { getCsrfTokenHeader } from "~/utils";

export function useCancelDockerServiceDeploymentMutation(
  project_slug: string,
  service_slug: string,
  deployment_hash: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const { error, data } = await apiClient.PUT(
        "/api/projects/{project_slug}/cancel-deployment/docker/{service_slug}/{deployment_hash}/",
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

      if (error) {
        const fullErrorMessage = error.errors
          .map((err) => err.detail)
          .join(" ");

        throw new Error(fullErrorMessage);
      }
      if (data) {
        await queryClient.invalidateQueries(
          serviceQueries.single({ project_slug, service_slug })
        );
        return;
      }
    }
  });
}
