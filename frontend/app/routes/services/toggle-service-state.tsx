import { redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { durationToMs, getCsrfTokenHeader, wait } from "~/utils";
import type { Route } from "./+types/toggle-service-state";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    `/project/${params.projectSlug}/${params.envSlug}/services/${params.serviceSlug}/settings`
  );
}

export type ToggleServiceState = RequestInput<
  "put",
  "/api/projects/{project_slug}/{env_slug}/toggle-service/{service_slug}/"
>["desired_state"];

export async function clientAction({
  params: {
    projectSlug: project_slug,
    serviceSlug: service_slug,
    envSlug: env_slug
  },
  request
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const userData = {
    desired_state: formData
      .get("desired_state")
      ?.toString()! as ToggleServiceState
  };
  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/toggle-service/{service_slug}/",
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
    serviceQueries.single({ project_slug, service_slug, env_slug })
  );

  return {
    success: true
  };
}
