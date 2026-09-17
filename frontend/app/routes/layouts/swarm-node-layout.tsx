import { useQuery } from "@tanstack/react-query";
import { SettingsIcon, TerminalIcon } from "lucide-react";
import { Outlet, href } from "react-router";
import { HorizontalNavLink } from "~/components/horizontal-nav-link";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn } from "~/lib/utils";
import type { Route } from "./+types/swarm-node-layout";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const node = await queryClient.ensureQueryData(
    swarmQueries.singleNode(params.serverId)
  );

  return {
    node
  };
}

export default function SwarmNodeLayout({
  params,
  loaderData
}: Route.ComponentProps) {
  const { data: node } = useQuery({
    ...swarmQueries.singleNode(params.serverId),
    initialData: loaderData.node
  });
  return (
    <div className="flex flex-col gap-4">
      <section className="flex items-center gap-4">
        <h2 className="text-2xl flex items-center gap-2">
          <div className="inline-flex gap-0.5 font-medium items-center group-hover:underline ">
            {node.hostname}
          </div>
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
              to={href("/admin/servers/:serverId", params)}
              prefetch="viewport"
            >
              <span>Details</span>
              <SettingsIcon size={15} className="flex-none" />
            </HorizontalNavLink>
          </li>
          <li>
            <HorizontalNavLink
              to={href("/admin/servers/:serverId/console", params)}
              prefetch="viewport"
            >
              <span>Console</span>
              <TerminalIcon size={15} className="flex-none" />
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
