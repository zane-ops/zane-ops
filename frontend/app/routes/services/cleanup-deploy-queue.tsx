import { redirect } from "react-router";

import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/cleanup-deploy-queue";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}/settings`
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
    "/api/projects/{project_slug}/{env_slug}/service-details/{service_slug}/cleanup-deployment-queue/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      body: {
        cancel_running_deployments:
          formData.get("cancel_running_deployments") === "on"
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
    return {
      errors: error
    };
  }

  await queryClient.invalidateQueries(
    serviceQueries.single({ project_slug, service_slug, env_slug })
  );
  toast.success("Success", {
    description: "Deployment queue cleaned up sucessfully !",
    closeButton: true
  });
  return { data };
}
