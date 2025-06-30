import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/deploy-git-service";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}`
  );
}

export async function clientAction({
  request,
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const { error, data } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/deploy-service/git/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        ignore_build_cache:
          formData.get("ignore_build_cache")?.toString() === "on",
        cleanup_queue: formData.get("cleanup_queue")?.toString() === "on"
      },
      params: {
        path: {
          project_slug,
          env_slug,
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
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    serviceQueries.single({ project_slug, service_slug, env_slug })
  );
  toast.success("Success", {
    description: "Deployment queued sucesfully !",
    closeButton: true
  });
  return { data };
}
