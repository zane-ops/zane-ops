import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { userQueries } from "~/lib/queries";

import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import type { Route } from "./+types/switch-workspace";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/workspace"));
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const formData = await request.formData();
  const userData = {
    workspace_id: formData.get("workspace_id")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/workspaces/switch/">;

  const { error } = await apiClient.POST("/api/workspaces/switch/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    body: userData
  });

  if (error) {
    const fullErrorMessage = error.errors
      .map((err) => `${err.attr}: ${err.detail}`)
      .join(" ");

    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return;
  }

  const queryClient = getQueryClient();

  const [authedUser] = await Promise.all([
    // `staleTime: 0` force refetch, while `fetchQuery` writes in the cache
    queryClient.fetchQuery({ ...userQueries.authedUser, staleTime: 0 }),
    queryClient.invalidateQueries(userQueries.memberships)
  ]);

  if (authedUser?.membership?.role_name === "Viewer") {
    throw redirect(href("/workspace/viewer"));
  }

  throw redirect(href("/workspace"));
}
