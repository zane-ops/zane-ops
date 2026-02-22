import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { composeStackQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/discard-compose-stack-change";

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
  const toastId = toast.loading("Discarding stack change...");
  const change_id = formData.get("change_id")?.toString()!;

  const { error: errors, data } = await apiClient.DELETE(
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
          change_id
        }
      }
    }
  );

  if (errors) {
    toast.error("Failed to discard change", { id: toastId, closeButton: true });
    return {
      errors
    };
  }

  await queryClient.invalidateQueries({
    ...composeStackQueries.single({ project_slug, stack_slug, env_slug }),
    exact: true
  });
  toast.success("Change discarded successfully", {
    id: toastId,
    closeButton: true
  });
  return {
    data
  };
}
