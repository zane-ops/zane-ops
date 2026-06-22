import { redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { ZANE_UPDATE_TOAST_ID } from "~/lib/constants";
import { serverQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { durationToMs, getCsrfTokenHeader, wait } from "~/utils";
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

  // poll the ongoing update status in the background and keep the user
  // informed with a loading toast until the update finishes
  pollUntilUpdateDone();

  return { data };
}

// guard against running multiple polling loops concurrently
let isPolling = false;

/**
 * Show a loading toast and poll the ongoing update status until ZaneOps
 * finished updating. Fire-and-forget: it runs in the background.
 */
export async function pollUntilUpdateDone() {
  if (isPolling) return;
  isPolling = true;

  toast.loading(
    "ZaneOps is updating in the background... Reload the page when this toast is closed",
    {
      id: ZANE_UPDATE_TOAST_ID,
      closeButton: false
    }
  );

  try {
    const deadline = Date.now() + durationToMs(5, "minutes");
    let updateOngoing = true;

    while (updateOngoing && Date.now() < deadline) {
      await wait(durationToMs(5, "seconds"));
      const data = await queryClient.fetchQuery(serverQueries.ongoingUpdate);
      updateOngoing = data?.update_ongoing ?? false;
    }

    if (updateOngoing) {
      toast.warning("ZaneOps is still updating", {
        description:
          "The update is taking longer than expected. Reload the page later to check if the new version is ready.",
        id: ZANE_UPDATE_TOAST_ID,
        closeButton: true,
        duration: Number.POSITIVE_INFINITY
      });
    } else {
      toast.success("ZaneOps updated successfully", {
        description: "Reload the page to use the new version.",
        id: ZANE_UPDATE_TOAST_ID,
        closeButton: true,
        duration: Number.POSITIVE_INFINITY
      });
    }
  } finally {
    isPolling = false;
  }
}
