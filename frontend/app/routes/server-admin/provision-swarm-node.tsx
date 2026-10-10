import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/provision-swarm-node";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(href("/admin/servers/:serverId", params));
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const formData = await request.formData();

  const userData = {
    target_ssh_key_id: formData
      .get("target_ssh_key_id")
      ?.toString() as unknown as number,
    main_ssh_key_id: formData
      .get("main_ssh_key_id")
      ?.toString() as unknown as number
  } satisfies RequestInput<"post", "/api/swarm/nodes/{id}/provision/">;

  const { error: errors, data } = await apiClient.POST(
    "/api/swarm/nodes/{id}/provision/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: params.serverId }
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      userData
    };
  }

  await queryClient.invalidateQueries({
    queryKey: swarmQueries.nodeList().queryKey.slice(0, 1)
  });

  toast.success("Success", {
    description: "Provisioning of the server has started",
    closeButton: true
  });

  throw redirect(
    href("/admin/servers/:serverId/deployment-logs", {
      serverId: params.serverId
    })
  );
}
