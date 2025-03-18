import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/toggle-service-state";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}/settings`
  );
}

export async function clientAction({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  }
}: Route.ClientActionArgs) {
  const deploymentList = queryClient.getQueryData(
    serviceQueries.deploymentList({ project_slug, service_slug, env_slug })
      .queryKey
  );

  const currentProductionDeployment = deploymentList?.results.find(
    (dpl) => dpl.is_current_production
  );
  const wasSleeping = currentProductionDeployment?.status == "SLEEPING";

  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/toggle-service/docker/{service_slug}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
          service_slug,
          env_slug
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
    closeButton: true,
    description: !wasSleeping
      ? "The service being put to sleep. It will take a few seconds to update."
      : "The service being restarted. It will take a few seconds to update."
  });
  return {
    success: true
  };
}
