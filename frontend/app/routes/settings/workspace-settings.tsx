import type { Route } from "./+types/workspace-settings";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceSettingsPage({}: Route.ComponentProps) {
  return <>workspace-settings Page</>;
}
