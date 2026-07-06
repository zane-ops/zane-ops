import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/discard-service-change";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}`
  );
}
export async function clientAction({
  request,
  params: {
    workspaceId,
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();
  const toastId = toast.loading("Discarding service change...");
  const change_id = formData.get("change_id")?.toString();

  const { error: errors, data } = await apiClient.DELETE(
    "/api/projects/{project_slug}/{env_slug}/cancel-service-changes/{service_slug}/{change_id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          env_slug,
          change_id: change_id!
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
    ...serviceQueries.single({
      workspaceId,
      project_slug,
      service_slug,
      env_slug
    }),
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
