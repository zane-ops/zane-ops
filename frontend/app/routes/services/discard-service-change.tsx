import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/discard-service-change";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/services/${params.serviceSlug}`
  );
}
export async function clientAction({
  request,
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const toastId = toast.loading("Discarding service change...");
  const change_id = formData.get("change_id")?.toString();

  const { error: errors, data } = await apiClient.DELETE(
    "/api/projects/{project_slug}/cancel-service-changes/docker/{service_slug}/{change_id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
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
    ...serviceQueries.single({ project_slug, service_slug }),
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
