import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/discard-multiple-changes";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/:workspaceId/project/:projectSlug/:envSlug/services/:serviceSlug",
      params
    )
  );
}

export async function clientAction({
  request,
  params: {
    workspaceId,
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();
  const changes = formData.getAll("change_id");
  let fullErrorMessage = "";
  const results = await Promise.all(
    changes.map(async (change_id) =>
      apiClient.DELETE(
        "/api/projects/{project_slug}/{env_slug}/cancel-service-changes/{service_slug}/{change_id}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              service_slug,
              env_slug,
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
    serviceQueries.single({ workspaceId, project_slug, service_slug, env_slug })
  );

  if (fullErrorMessage) {
    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors: results.flat()
    };
  }

  toast.success("Success", {
    description: "Changes discarded successfully !",
    closeButton: true
  });
  return {};
}
