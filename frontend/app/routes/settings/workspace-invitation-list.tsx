import { ensureMinRole, workspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { metaTitle } from "~/lib/utils";
import { getCurrentWorkspace } from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-invitation-list";

export function meta() {
  return [
    metaTitle("Workspace Invitations")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
  const workspace = await getCurrentWorkspace(queryClient);

  const invitations = await queryClient.ensureQueryData(
    workspaceQueries.invitations(workspace.id)
  );
  return {
    invitations
  };
}

export default function WorkspaceInvitationListPage({}: Route.ComponentProps) {
  return <>workspace-invitations-list Page</>;
}
