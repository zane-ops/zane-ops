import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { composeStackQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/cancel-compose-deployment";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/workspace/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments/:deploymentHash",
      params
    )
  );
}

export async function clientAction({ params }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const toastId = toast.loading(
    `Requesting cancellation for deployment #${params.deploymentHash}...`
  );

  const { error } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deployments/{hash}/cancel/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: params.projectSlug,
          slug: params.composeStackSlug,
          hash: params.deploymentHash,
          env_slug: params.envSlug
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      id: toastId,
      closeButton: true
    });
    return;
  }

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  await Promise.all([
    queryClient.invalidateQueries({
      ...composeStackQueries.singleDeployment({
        workspaceId: workspaceId,
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        deployment_hash: params.deploymentHash
      }),
      exact: true
    }),
    queryClient.invalidateQueries(
      composeStackQueries.deploymentList({
        workspaceId: workspaceId,
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug
      })
    )
  ]);
  toast.success("Success", {
    description: "Deployment cancel request sent.",
    id: toastId,
    closeButton: true
  });
}
