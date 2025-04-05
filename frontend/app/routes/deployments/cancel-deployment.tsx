import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/cancel-deployment";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}/deployments/${params.deploymentHash}`
  );
}

export async function clientAction({
  params,
  request
}: Route.ClientActionArgs) {
  const toastId = toast.loading(
    `Requesting cancellation for deployment #${params.deploymentHash}...`
  );
  const formData = await request.formData();
  const shouldRedirect = formData.get("do_not_redirect")?.toString() !== "true";

  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/cancel-deployment/{service_slug}/{deployment_hash}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug: params.projectSlug,
          service_slug: params.serviceSlug,
          deployment_hash: params.deploymentHash,
          env_slug: params.envSlug
        }
      }
    }
  );

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      id: toastId,
      closeButton: true
    });
    if (shouldRedirect) {
      throw redirect(
        `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}`
      );
    }
    return;
  }

  await queryClient.invalidateQueries({
    ...serviceQueries.single({
      project_slug: params.projectSlug,
      service_slug: params.serviceSlug,
      env_slug: params.envSlug
    }),
    exact: true
  });
  toast.success("Success", {
    description: "Deployment cancel request sent.",
    id: toastId,
    closeButton: true
  });
  if (shouldRedirect) {
    throw redirect(
      `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}`
    );
  }
}
