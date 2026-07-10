import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { environmentQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { ErrorResponseFromAPI } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/archive-compose-stack";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      "/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug/settings",
      params
    )
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();

  if (
    formData.get("stack_slug")?.toString().trim() !==
    `${params.projectSlug}/${params.envSlug}/${params.composeStackSlug}`
  ) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "stack_slug",
            code: "invalid",
            detail: "The slug does not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const { error } = await apiClient.DELETE(
    "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/archive/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: params.projectSlug,
          env_slug: params.envSlug,
          slug: params.composeStackSlug
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

  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  await queryClient.invalidateQueries(
    environmentQueries.composeStackList(
      workspaceId,
      params.projectSlug,
      params.envSlug
    )
  );
  toast.success("Success", {
    description: "Compose Stack deleted succesfully !",
    closeButton: true
  });

  throw redirect(href("/project/:projectSlug/:envSlug", params));
}
