import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { serverQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/trigger-update";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(`/`);
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const { error, data } = await apiClient.POST("/api/trigger-update/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: {
      desired_version: formData.get("desired_version")?.toString()!
    }
  });

  if (error) {
    const fullErrorMessage = error.errors.map((err) => err.detail).join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors: error.errors
    };
  }

  await queryClient.invalidateQueries(serverQueries.ongoingUpdate);

  toast.success("Success", {
    description:
      "Update in progress, it might take a while..." +
      " You can reload the page when the new version is ready.",
    closeButton: true
  });
  return { data };
}
