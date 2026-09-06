import type { Route } from "./+types/workspace-api-tokens";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceAPITokensPage({}: Route.ComponentProps) {
  return <>api-tokens Page</>;
}
