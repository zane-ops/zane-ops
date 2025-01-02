import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/redeploy-old-deployment";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/services/${params.serviceSlug}`
  );
}

export async function clientAction({ params }: Route.ClientActionArgs) {
  const toasId = toast.loading(
    `Queuing redeployment for #${params.deploymentHash}...`
  );
  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/deploy-service/docker/{service_slug}/{deployment_hash}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: params.projectSlug,
          service_slug: params.serviceSlug,
          deployment_hash: params.deploymentHash
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");
    toast.error("Error", {
      description: fullErrorMessage,
      id: toasId,
      closeButton: true
    });
    throw redirect(
      `/project/${params.projectSlug}/services/${params.serviceSlug}`
    );
  }

  await queryClient.invalidateQueries(
    serviceQueries.single({
      project_slug: params.projectSlug,
      service_slug: params.serviceSlug
    })
  );
  toast.success("Success", {
    description: "Redeployment queued succesfully.",
    id: toasId,
    closeButton: true
  });
  throw redirect(
    `/project/${params.projectSlug}/services/${params.serviceSlug}`
  );
}
