import { href, redirect } from "react-router";
import { type RequestInput, apiClient } from "~/api/client";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/create-swarm-node-ssh-key";

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
    slug: formData.get("slug")?.toString() ?? "",
    user: formData.get("user")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/swarm/nodes/{id}/ssh-keys/">;

  const { error: errors, data } = await apiClient.POST(
    "/api/swarm/nodes/{id}/ssh-keys/",
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

  return {
    data
  };
}
