import { href, redirect } from "react-router";
import { ensureMinRole } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/workspace-remove-member";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "Admin");
  throw redirect(href("/workspace/settings"));
}

export default function RemoveWorkspaceMemberPage({}: Route.ComponentProps) {
  return <>workspace-remove-member Page</>;
}
