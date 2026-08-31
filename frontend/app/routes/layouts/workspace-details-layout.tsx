import { useQuery } from "@tanstack/react-query";
import { SettingsIcon, UsersIcon } from "lucide-react";
import { Outlet, href } from "react-router";
import { HorizontalNavLink } from "~/components/horizontal-nav-link";
import { adminWorkspaceQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, stringToColor } from "~/lib/utils";
import type { Route } from "./+types/workspace-details-layout";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const workspace = await queryClient.ensureQueryData(
    adminWorkspaceQueries.single(params.workspaceId)
  );
  return { workspace };
}

export default function WorkspaceDetailsLayout({
  params,
  loaderData
}: Route.ComponentProps) {
  const { data: workspace } = useQuery({
    ...adminWorkspaceQueries.single(params.workspaceId),
    initialData: loaderData.workspace
  });

  const color = stringToColor(workspace.name);

  return (
    <div className="flex flex-col gap-4">
      <section className="flex items-center gap-4">
        <h2
          className="text-2xl flex items-center gap-2"
          style={
            {
              "--color-light": color.light,
              "--color-dark": color.dark
            } as React.CSSProperties
          }
        >
          <div
            className={cn(
              "size-10 flex-none rounded-md flex items-center justify-center",
              "text-(--color-light) dark:text-(--color-dark)",
              "bg-(--color-light)/10 dark:bg-(--color-dark)/10",
              "border border-(--color-light)/10 dark:border-(--color-dark)/10"
            )}
          >
            <span>{workspace.name.charAt(0).toUpperCase()}</span>
          </div>
          <span>
            <div className="inline-flex gap-0.5 font-medium items-center group-hover:underline ">
              {workspace.name}
            </div>
          </span>
        </h2>
      </section>

      <nav>
        <ul
          className={cn(
            "overflow-x-auto overflow-y-clip h-[2.55rem] w-full items-start justify-start rounded-none border-b border-border ",
            "inline-flex items-stretch p-0.5 text-muted-foreground"
          )}
        >
          <li>
            <HorizontalNavLink
              to={href("/admin/workspaces/:workspaceId", params)}
              prefetch="viewport"
            >
              <span>Settings</span>
              <SettingsIcon size={15} className="flex-none" />
            </HorizontalNavLink>
          </li>
          <li>
            <HorizontalNavLink
              to={href("/admin/workspaces/:workspaceId/members", params)}
              prefetch="viewport"
            >
              <span>Members</span>
              <UsersIcon size={15} className="flex-none" />
            </HorizontalNavLink>
          </li>
        </ul>
      </nav>

      <section>
        <Outlet />
      </section>
    </div>
  );
}
