import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { composeStackQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/redeploy-compose-deployment";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments/:deploymentHash",
      params
    )
  );
}

export async function clientAction({ params }: Route.ClientActionArgs) {
  const toastId = toast.loading(
    `Queueing redeployment for #${params.deploymentHash}...`
  );

  const { error } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deploy/{hash}/",
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
    throw redirect(
      href(
        "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/deployments",
        params
      )
    );
  }

  await Promise.all([
    queryClient.invalidateQueries({
      ...composeStackQueries.singleDeployment({
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug,
        deployment_hash: params.deploymentHash
      }),
      exact: true
    }),
    queryClient.invalidateQueries(
      composeStackQueries.deploymentList({
        project_slug: params.projectSlug,
        stack_slug: params.composeStackSlug,
        env_slug: params.envSlug
      })
    )
  ]);
  toast.success("Success", {
    description: "Redeployment queued succesfully.",
    id: toastId,
    closeButton: true
  });
}
