import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/redeploy-docker-deployment";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href("/project/:projectSlug/:envSlug/services/:serviceSlug", params)
  );
}

export async function clientAction({ params }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const toasId = toast.loading(
    `Queueing redeployment for #${params.deploymentHash}...`
  );
  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/redeploy-service/docker/{service_slug}/{deployment_hash}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: params.projectSlug,
          service_slug: params.serviceSlug,
          deployment_hash: params.deploymentHash,
          env_slug: params.envSlug
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");
    toast.error("Error", {
      description: fullErrorMessage,
      id: toasId,
      closeButton: true
    });
    throw redirect(
      href("/project/:projectSlug/:envSlug/services/:serviceSlug", params)
    );
  }

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  await queryClient.invalidateQueries(
    serviceQueries.single({
      workspaceId,
      project_slug: params.projectSlug,
      service_slug: params.serviceSlug,
      env_slug: params.envSlug
    })
  );
  toast.success("Success", {
    description: "Redeployment queued succesfully.",
    id: toasId,
    closeButton: true
  });
  throw redirect(
    href("/project/:projectSlug/:envSlug/services/:serviceSlug", params)
  );
}
