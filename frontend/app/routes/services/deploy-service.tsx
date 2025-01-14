import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/deploy-service";

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
  const { error, data } = await apiClient.PUT(
    "/api/projects/{project_slug}/deploy-service/docker/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        commit_message: formData.get("commit_message")?.toString()
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
  if (data) {
    await queryClient.invalidateQueries(
      serviceQueries.single({ project_slug, service_slug })
    );
    toast.success("Success", {
      description: "Deployment queued sucesfully !",
      closeButton: true
    });
    return;
  }
}
