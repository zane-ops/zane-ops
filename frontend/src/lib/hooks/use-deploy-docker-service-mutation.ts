import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type RequestInput, apiClient } from "~/api/client";
import { serviceKeys } from "~/key-factories";
import { getCsrfTokenHeader } from "~/utils";

export function useDeployDockerServiceMutation(
  project_slug: string,
  service_slug: string
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      input: RequestInput<
        "put",
        "/api/projects/{project_slug}/deploy-service/docker/{service_slug}/"
      >
    ) => {
      const { error, data } = await apiClient.PUT(
        "/api/projects/{project_slug}/deploy-service/docker/{service_slug}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          body: input,
          params: {
            path: {
              project_slug,
              service_slug
            }
          }
        }
      );

      if (error) return error;
      if (data) {
        await queryClient.invalidateQueries({
          queryKey: serviceKeys.single(project_slug, service_slug, "docker")
        });
        return;
      }
    }
  });
}
