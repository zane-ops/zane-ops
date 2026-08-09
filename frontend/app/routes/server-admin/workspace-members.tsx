import type { Route } from "./+types/workspace-members";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceMembersPage({}: Route.ComponentProps) {
  return <>workspace-members Page</>;
}
