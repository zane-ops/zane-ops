import { href, redirect } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import { workspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-invitation-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/settings/invitations"));
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();

  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "delete":
      return deleteInvitation(params);
    case "regenerate-link":
      return regenerateInvitationLink(formData, params);
    default: {
      throw new Error(`Unexpected intent \`${intent}\``);
    }
  }
}

async function deleteInvitation(params: Route.ComponentProps["params"]) {
  const queryClient = getQueryClient();
  const workspace = await getCurrentWorkspace(queryClient);

  const { error: errors, data } = await apiClient.DELETE(
    "/api/workspace/invitations/{id}/delete/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: params.id }
      }
    }
  );

  if (errors) {
    const fullErrorMessage = errors.errors.map((err) => err.detail).join(" ");
    toast.error("Error", {
      description: fullErrorMessage,
      closeButton: true
    });
    return {
      errors,
      data,
      userData: undefined
    };
  }

  toast.success("Success", {
    description: "Invitation successfully removed.",
    closeButton: true
  });

  await queryClient.invalidateQueries({
    queryKey: workspaceQueries.invitations(workspace.id).queryKey.slice(0, 3)
  });
  throw redirect(href("/settings/invitations"));
}

async function regenerateInvitationLink(
  formData: FormData,
  params: Route.ComponentProps["params"]
) {
  const queryClient = getQueryClient();
  const workspace = await getCurrentWorkspace(queryClient);

  type Body = RequestInput<
    "put",
    "/api/workspace/invitations/{id}/regenerate/"
  >;

  const userData = {
    valid_for: Number(
      formData.get("valid_for")?.toString() ?? ""
    ) as Body["valid_for"]
  } satisfies Body;

  const { error: errors, data } = await apiClient.PUT(
    "/api/workspace/invitations/{id}/regenerate/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: params.id }
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      data,
      userData: undefined
    };
  }

  await queryClient.invalidateQueries({
    queryKey: workspaceQueries.invitations(workspace.id).queryKey.slice(0, 3)
  });

  return { data, errors: undefined, userData };
}
