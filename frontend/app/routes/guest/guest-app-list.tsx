import { ensureMinRole } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/guest-app-list";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Guest");

  return;
}

export default function GuestAppsListPage({}: Route.ComponentProps) {
  return <>guest-apps-list Page</>;
}
