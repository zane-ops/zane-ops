import { Outlet } from "react-router";
import { ensureMinRole } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { metaTitle } from "~/lib/utils";
import type { Route } from "./+types/server-admin-layout";

export function meta() {
  return [metaTitle("Server Admin")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "ServerAdmin");
  return;
}

export default function ServerAdminLayout({}: Route.ComponentProps) {
  return (
    <>
      <Outlet />
    </>
  );
}
