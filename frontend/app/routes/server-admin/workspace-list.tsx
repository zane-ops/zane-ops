import type { Route } from "./+types/workspace-list";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceListPage({}: Route.ComponentProps) {
  return <>workspace-list Page</>;
}
