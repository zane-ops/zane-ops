import { Outlet } from "react-router";
import { CommandBar } from "~/components/commandbar/commandbar";
import { SERVER_ADMIN_NAV_GROUPS } from "~/components/commandbar/commandbar-nav-items";
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
      <CommandBar navItems={SERVER_ADMIN_NAV_GROUPS} />
      <Outlet />
    </>
  );
}
