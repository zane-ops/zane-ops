import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";

import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/switch-workspace";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/workspace"));
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const currentWorkspace = await getCurrentWorkspace(getQueryClient());

  const formData = await request.formData();
  const userData = {
    workspace_id: formData.get("workspace_id")?.toString() ?? ""
  } satisfies RequestInput<"post", "/api/workspaces/switch/">;

  if (currentWorkspace.id === userData.workspace_id) return;

  toast.loading("Loading", {
    description: "Switching workspaces...",
    dismissible: false,
    closeButton: false
  });

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

  window.location.href = href("/workspace");
}
