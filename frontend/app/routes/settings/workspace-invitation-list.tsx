import type { Route } from "./+types/workspace-invitation-list";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceInvitationListPage({}: Route.ComponentProps) {
  return <>workspace-invitations-list Page</>;
}
