import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { getCsrfTokenHeader } from "~/utils";

export function useCancelDockerServiceChangeMutation(
  project_slug: string,
  service_slug: string
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (change_id: string) => {
      const { error, data } = await apiClient.DELETE(
        "/api/projects/{project_slug}/cancel-service-changes/docker/{service_slug}/{change_id}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              service_slug,
              change_id
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
        await queryClient.invalidateQueries({
          ...serviceQueries.single({ project_slug, service_slug }),
          exact: true
        });
        return;
      }
    }
  });
}
