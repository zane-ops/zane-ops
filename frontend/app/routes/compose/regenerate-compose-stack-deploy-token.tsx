import type { Route } from "./+types/regenerate-compose-stack-deploy-token";

import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { composeStackQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/settings",
      params
    )
  );
}

export async function clientAction({
  params: {
    projectSlug: project_slug,
    envSlug: env_slug,
    composeStackSlug: stack_slug
  }
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const { error, data } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/regenerate-deploy-token/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          env_slug,
          slug: stack_slug
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
    composeStackQueries.single({
      workspaceId,
      project_slug,
      stack_slug,
      env_slug
    })
  );
  toast.success("Success", {
    description: "Done",
    closeButton: true
  });
  return { data };
}
