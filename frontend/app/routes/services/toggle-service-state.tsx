import { redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { serviceQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { durationToMs, getCsrfTokenHeader, wait } from "~/utils";
import { type Route } from "./+types/toggle-service-state";

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

  const MAX_TRIES = 3;
  let total_tries = 0;
  const deploymentList =
    (await queryClient.getQueryData(
      serviceQueries.deploymentList({
        project_slug,
        service_slug,
        env_slug
      }).queryKey
    )?.results) ?? [];

  let currentProductionDeployment =
    deploymentList.find((dpl) => dpl.is_current_production) ?? null;

  let currentState: ToggleServiceState | null = null;

  while (
    total_tries < MAX_TRIES &&
    currentProductionDeployment !== null &&
    currentState !== userData.desired_state
  ) {
    total_tries++;

    const deploymentList =
      (await queryClient.getQueryData(
        serviceQueries.deploymentList({
          project_slug,
          service_slug,
          env_slug
        }).queryKey
      )?.results) ?? [];
    currentProductionDeployment =
      deploymentList.find((dpl) => dpl.is_current_production) ?? null;

    if (currentProductionDeployment) {
      currentState =
        currentProductionDeployment.status === "SLEEPING" ? "stop" : "start";
    }

    if (currentState !== userData.desired_state && total_tries < MAX_TRIES) {
      await wait(durationToMs(5, "seconds"));
    }
  }

  toast.success("Success", {
    closeButton: true,
    description:
      userData.desired_state === "stop"
        ? "The service being put to sleep. It will take a few seconds to update."
        : "The service being restarted. It will take a few seconds to update."
  });
  return {
    success: true
  };
}
