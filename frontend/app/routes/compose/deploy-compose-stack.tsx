import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import {
  composeStackQueries,
  serviceQueries,
  userQueries
} from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/deploy-compose-stack";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug",
      params
    )
  );
}

export async function clientAction({
  request,
  params: {
    projectSlug: project_slug,
    composeStackSlug: stack_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();

  const commit_message = formData.get("commit_message")?.toString();

  const { error, data } = await apiClient.PUT(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/deploy/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        commit_message: commit_message ? commit_message : undefined
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

  await Promise.all([
    queryClient.invalidateQueries(
      composeStackQueries.single({
        workspaceId,
        project_slug,
        stack_slug,
        env_slug
      })
    ),
    queryClient.invalidateQueries(
      composeStackQueries.deploymentList({
        workspaceId,
        project_slug,
        stack_slug,
        env_slug
      })
    )
  ]);
  toast.success("Success", {
    description: "Deployment queued sucesfully !",
    closeButton: true
  });
  return { data };
}
