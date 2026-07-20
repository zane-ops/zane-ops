import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { getCurrentWorkspace } from "~/lib/auth-store";
import { environmentQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { type Route } from "./+types/bulk-toggle-service-state";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(href("/workspace/project/:projectSlug/:envSlug", params));
}

export async function clientAction({
  params: { projectSlug: project_slug, envSlug: env_slug },
  request
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const formData = await request.formData();
  const userData = {
    desired_state: formData.get("desired_state")?.toString()! as
      | "start"
      | "stop",
    service_ids: formData.getAll("service_id").map((data) => data.toString())
  };
  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/bulk-toggle-services/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          env_slug
        }
      },
      body: userData
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
    environmentQueries.serviceList(workspaceId, project_slug, env_slug)
  );

  toast.success("Success", {
    closeButton: true,
    description:
      userData.desired_state === "stop"
        ? "Services are being put to sleep. It will take a few seconds to update."
        : "Services are being restarted. It will take a few seconds to update."
  });
  return {
    success: true
  };
}
