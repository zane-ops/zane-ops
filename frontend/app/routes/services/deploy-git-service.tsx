import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/deploy-git-service";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug",
      params
    )
  );
}

export async function clientAction({
  request,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();

  const { error, data } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/deploy-service/git/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        ignore_build_cache:
          formData.get("ignore_build_cache")?.toString() === "on",
        cleanup_queue: formData.get("cleanup_queue")?.toString() === "on"
      },
      params: {
        path: {
          project_slug,
          env_slug,
          service_slug
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    serviceQueries.single({ workspaceId, project_slug, service_slug, env_slug })
  );
  toast.success("Success", {
    description: "Deployment queued sucesfully !",
    closeButton: true
  });
  return { data };
}
