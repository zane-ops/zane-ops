import { href, redirect } from "react-router";

import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/cleanup-deploy-queue";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/workspace/project/:projectSlug/:envSlug/services/:serviceSlug/settings",
      {
        ...params
      }
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
    "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/cleanup-deployment-queue/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        cancel_running_deployments:
          formData.get("cancel_running_deployments") === "on"
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
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    serviceQueries.single({ workspaceId, project_slug, service_slug, env_slug })
  );
  toast.success("Success", {
    description: "Deployment queue cleaned up sucessfully !",
    closeButton: true
  });
  return { data };
}
