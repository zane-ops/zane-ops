import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/discard-multiple-changes";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/services/${params.serviceSlug}`
  );
}

export async function clientAction({
  request,
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const changes = formData.getAll("change_id");
  let fullErrorMessage = "";
  const results = await Promise.all(
    changes.map(async (change_id) =>
      apiClient.DELETE(
        "/api/projects/{project_slug}/cancel-service-changes/docker/{service_slug}/{change_id}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              service_slug,
              change_id: change_id.toString()
            }
          }
        }
      )
    )
  );

  for (const result of results) {
    if (result.error) {
      fullErrorMessage += result.error.errors
        .map((err) => err.detail)
        .join(" ");
    }
  }

  await queryClient.invalidateQueries(
    serviceQueries.single({ project_slug, service_slug })
  );

  if (fullErrorMessage) {
    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors: results.map((errors) => errors).flat()
    };
  }

  toast.success("Success", {
    description: "Changes discarded successfully !",
    closeButton: true
  });
  return {};
}
