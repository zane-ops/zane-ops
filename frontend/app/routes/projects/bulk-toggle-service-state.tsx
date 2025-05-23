import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { projectQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import { type Route } from "./+types/bulk-toggle-service-state";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(`/project/${params.projectSlug}/${params.envSlug}`);
}

export async function clientAction({
  params: { projectSlug: project_slug, envSlug: env_slug },
  request
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const userData = {
    desired_state: formData.get("desired_state")?.toString()! as
      | "start"
      | "stop",
    service_ids: formData.getAll("service_id").map((data) => data.toString())
  };
  const { error } = await apiClient.PUT(
    "/api/projects/{project_slug}/{env_slug}/bulk-toggle-services/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          project_slug,
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
    projectQueries.serviceList(project_slug, env_slug)
  );

  toast.success("Success", {
    closeButton: true,
    description:
      userData.desired_state === "stop"
        ? "Services are being put to sleep. It will take a few seconds to update."
        : "Services are being restarted. It will take a few seconds to update."
  });
  return {
    success: true
  };
}
