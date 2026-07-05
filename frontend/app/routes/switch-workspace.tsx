import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { userQueries } from "~/lib/queries";
import { queryClient } from "~/root";
import { getCsrfTokenHeader } from "~/utils";
import type { Route } from "./+types/switch-workspace";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(`/`);
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

  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: userQueries.authedUser.queryKey
    }),
    queryClient.invalidateQueries({
      predicate(query) {
        return query.queryKey[0] === userQueries.currentWorkspace.queryKey[0];
      }
    })
  ]);

  throw redirect(href("/:workspaceId", { workspaceId: userData.workspace_id }));
}
