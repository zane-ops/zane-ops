import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/cancel-swarm-node-provision";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(href("/admin/servers/:serverId", params));
}

export async function clientAction({ params }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const toastId = toast.loading(
    "Requesting cancellation of the provisioning..."
  );

  const { error } = await apiClient.PUT(
    "/api/swarm/nodes/{id}/cancel-provision/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: params.serverId }
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
    return;
  }

  await Promise.all([
    queryClient.invalidateQueries(swarmQueries.singleNode(params.serverId)),
    queryClient.invalidateQueries({
      queryKey: swarmQueries.nodeList().queryKey.slice(0, 1)
    })
  ]);

  toast.success("Success", {
    description: "Provisioning cancel request sent.",
    id: toastId,
    closeButton: true
  });
}
