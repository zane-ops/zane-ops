import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { projectQueries, serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/archive-service";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/services/${params.serviceSlug}/settings`
  );
}

export async function clientAction({
  params: { projectSlug: project_slug, serviceSlug: service_slug }
}: Route.ClientActionArgs) {
  const { error } = await apiClient.DELETE(
    "/api/projects/{project_slug}/archive-service/docker/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug
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
    return;
  }

  queryClient.removeQueries({
    queryKey: serviceQueries.single({ project_slug, service_slug }).queryKey
  });
  queryClient.invalidateQueries(projectQueries.serviceList(project_slug));

  toast.success("Success", {
    closeButton: true,
    description: `Service ${service_slug} has been succesfully archived.`
  });
  throw redirect(`/project/${project_slug}`);
}
