import { useQuery } from "@tanstack/react-query";
import {
  CrownIcon,
  NetworkIcon,
  SettingsIcon,
  TerminalIcon
} from "lucide-react";
import { Outlet, href } from "react-router";
import { HorizontalNavLink } from "~/components/horizontal-nav-link";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { capitalizeText, cn, metaTitle } from "~/lib/utils";
import { ServerStatusBadge } from "~/routes/server-admin/server-list";
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

  const status_emoji_map = {
    READY: "🟢",
    DOWN: "🔴",
    FAILED: "❌",
    DRAINED: "🗑️",
    PROVISIONING: "▶️"
  } satisfies Record<(typeof node)["status"], string>;

  const { title } = metaTitle(
    `${status_emoji_map[node.status]} ${capitalizeText(node.hostname)}`
  );

  return (
    <>
      <title>{title}</title>
      <div className="flex flex-col gap-4">
        <section className="flex items-center gap-3">
          <h2 className="text-2xl flex items-center gap-2">
            <div className="inline-flex gap-0.5 font-medium items-center group-hover:underline">
              {capitalizeText(node.hostname)}
            </div>
          </h2>

          <span className="inline-block rounded-full size-0.5 bg-foreground relative top-0.5" />

          <div className="flex items-center gap-1">
            {node.is_initial_install_server && (
              <div className="py-1 text-sm rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center">
                <CrownIcon className="size-4 flex-none" />
                <p>Main server</p>
              </div>
            )}
            <ServerStatusBadge status={node.status} className="text-sm" />
          </div>
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
            <li>
              <HorizontalNavLink
                to={href("/admin/servers/:serverId/services", params)}
                prefetch="viewport"
              >
                <span>Containers</span>
                <NetworkIcon size={15} className="flex-none" />
              </HorizontalNavLink>
            </li>
          </ul>
        </nav>

        <section>
          <Outlet />
        </section>
      </div>
    </>
  );
}
