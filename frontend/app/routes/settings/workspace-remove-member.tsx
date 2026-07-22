import { href, redirect } from "react-router";
import { toast } from "sonner";
import { apiClient } from "~/api/client";
import { getCurrentWorkspace } from "~/lib/auth-store";
import { ensureMinRole, workspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { getCsrfTokenHeader, getUserDisplayName } from "~/lib/utils";
import type { Route } from "./+types/workspace-remove-member";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  await ensureMinRole(getQueryClient(), "Admin");
  throw redirect(href("/workspace/settings"));
}

export async function clientAction({ params }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);

  const member = await queryClient.ensureQueryData(
    workspaceQueries.member(workspaceId, params.id)
  );

  const { error: errors, data } = await apiClient.DELETE(
    "/api/workspace/members/{membership_id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: {
          membership_id: params.id
        }
      }
    }
  );

  if (errors) {
    return {
      errors,
      data
    };
  }
  toast.success("Success", {
    dismissible: true,
    closeButton: true,
    description: (
      <p>
        <strong className="text-grey">
          &ldquo;{member.user.username}&rdquo;
        </strong>{" "}
        no longer has access to this workspace.
      </p>
    )
  });

  await queryClient.invalidateQueries({
    queryKey: workspaceQueries.members(workspaceId).queryKey.slice(0, 3)
  });

  throw redirect(href("/workspace/settings/team"));
}
