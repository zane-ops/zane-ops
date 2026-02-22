import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { composeStackQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/discard-compose-stack-multiple-changes";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href(
      `/project/:projectSlug/:envSlug/compose-stacks/:composeStackSlug`,
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
  const formData = await request.formData();
  const changes = formData.getAll("change_id");
  let fullErrorMessage = "";
  const results = await Promise.all(
    changes.map(async (change_id) =>
      apiClient.DELETE(
        "/api/compose/stacks/{project_slug}/{env_slug}/{slug}/cancel-changes/{change_id}/",
        {
          headers: {
            ...(await getCsrfTokenHeader())
          },
          params: {
            path: {
              project_slug,
              slug: stack_slug,
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

  await queryClient.invalidateQueries({
    ...composeStackQueries.single({ project_slug, stack_slug, env_slug }),
    exact: true
  });

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
