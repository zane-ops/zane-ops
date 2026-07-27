import { ensureMinRole } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/viewer-app-list";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Viewer");

  return;
}

export default function ViewerAppsListPage({}: Route.ComponentProps) {
  return <>viewer-apps-list Page</>;
}
