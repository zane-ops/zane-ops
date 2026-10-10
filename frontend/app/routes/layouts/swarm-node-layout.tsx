import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CrownIcon,
  HammerIcon,
  ContainerIcon,
  InfoIcon,
  LoaderIcon,
  ServerIcon,
  SettingsIcon,
  SquareChartGanttIcon,
  TerminalIcon
} from "lucide-react";
import * as React from "react";
import { Outlet, href, useFetcher } from "react-router";
import type { FullSwarmNode, SwarmNode } from "~/api/types";
import { Code } from "~/components/code";
import { HorizontalNavLink } from "~/components/horizontal-nav-link";
import { RootSSHKeySelect } from "~/components/root-ssh-key-select";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  capitalizeText,
  cn,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { clientAction as cancelProvisionClientAction } from "~/routes/server-admin/cancel-swarm-node-provision";
import type { clientAction } from "~/routes/server-admin/provision-swarm-node";
import { ServerStatusBadge } from "~/routes/server-admin/swarm-node-list";
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
    CREATED: "🆕",
    ACTIVE: "💚",
    DOWN: "🔴",
    UNHEALTHY: "💔",
    FAILED: "❌",
    DRAINED: "⏸️",
    PAUSED: "⏸️",
    PROVISIONING: "▶️",
    REMOVED: "🗑️"
  } satisfies Record<SwarmNode["status"], string>;

  const { title } = metaTitle(
    `${status_emoji_map[node.status]} ${capitalizeText(node.hostname ?? node.private_ip)}`
  );

  const isNotMemberOfClusterYet = ["CREATED", "FAILED", "REMOVED"].includes(
    node.status
  );
  const isProvisionCancellable =
    node.status === "PROVISIONING" && !node.is_initial_install_server;

  return (
    <>
      <title>{title}</title>
      <div className="flex flex-col gap-4">
        <section className="flex items-center gap-3">
          <h2 className="text-2xl flex items-center gap-2">
            <ServerIcon className="size-6 text-grey" />
            <div className="inline-flex gap-0.5 font-medium items-center group-hover:underline whitespace-nowrap">
              {capitalizeText(node.hostname ?? node.private_ip)}
            </div>
          </h2>

          <span className="inline-block rounded-full size-0.5 bg-foreground relative top-0.5" />

          <div className="flex justify-between items-center w-full">
            <div className="flex items-center gap-1">
              {node.is_initial_install_server && (
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <div className="cursor-help py-1 text-sm rounded-md bg-link/20 text-link px-2  inline-flex gap-1 items-center">
                        <CrownIcon className="size-4 flex-none" />
                        <p>Main server</p>
                        <InfoIcon className="size-3 flex-none" />
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64 text-pretty">
                      This is the server where ZaneOps was initially installed.
                      It runs the ZaneOps core services (API, proxy, database)
                      and cannot be removed from the cluster.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}

              <ServerStatusBadge status={node.status} className="text-sm" />
            </div>
            {isNotMemberOfClusterYet && <ProvisionSwarmNodeForm node={node} />}
            {isProvisionCancellable && (
              <CancelSwarmNodeProvisionForm node={node} />
            )}
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
                <SettingsIcon className="size-4 flex-none" />
              </HorizontalNavLink>
            </li>
            <li>
              <HorizontalNavLink
                to={href("/admin/servers/:serverId/console", params)}
                prefetch="viewport"
              >
                <span>Console</span>
                <TerminalIcon className="size-4 flex-none" />
              </HorizontalNavLink>
            </li>
            <li>
              <HorizontalNavLink
                to={href("/admin/servers/:serverId/deployment-logs", params)}
                prefetch="viewport"
              >
                <span>Deployment logs</span>
                <SquareChartGanttIcon className="size-4 flex-none" />
              </HorizontalNavLink>
            </li>
            <li>
              <HorizontalNavLink
                to={href("/admin/servers/:serverId/services", params)}
                prefetch="viewport"
              >
                <span>Services</span>
                <ContainerIcon className="size-4 flex-none" />
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

type ProvisionSwarmNodeFormProps = {
  node: FullSwarmNode;
};

function ProvisionSwarmNodeForm({ node }: ProvisionSwarmNodeFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const [open, setOpen] = React.useState(false);
  const [data, setData] = React.useState(fetcher.data);
  const isPending = fetcher.state !== "idle";

  const { data: mainNode, isLoading: isLoadingMainNode } = useQuery({
    ...swarmQueries.mainNode,
    enabled: open
  });

  const targetRootKeys = node.ssh_keys.filter((key) => key.user === "root");
  const mainRootKeys = (mainNode?.ssh_keys ?? []).filter(
    (key) => key.user === "root"
  );

  const errors = getFormErrorsFromResponseData(data?.errors);

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data === undefined) {
      setOpen(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.state, fetcher.data]);

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        if (isPending) return;
        setOpen(open);
        if (!open) setData(undefined);
      }}
    >
      <DialogTrigger asChild>
        <Button className="gap-1.5" size="sm">
          <HammerIcon className="size-4 flex-none" />
          Provision node
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0 max-w-xl">
        <DialogHeader className="pb-4">
          <DialogTitle>Provision this server</DialogTitle>
          <DialogDescription>
            ZaneOps will need to connect to both this server and the main server
            as <Code>root</Code> to install Docker and join this server to the
            cluster.
          </DialogDescription>

          {errors.non_field_errors && (
            <Alert variant="destructive" className="mt-5">
              <AlertCircleIcon className="size-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{errors.non_field_errors}</AlertDescription>
            </Alert>
          )}
        </DialogHeader>

        <fetcher.Form
          method="post"
          action={href("/admin/servers/:serverId/provision", {
            serverId: node.id
          })}
          id="provision-swarm-node-form"
          className="flex flex-col gap-4 mb-5"
        >
          <RootSSHKeySelect
            name="target_ssh_key_id"
            label="Root SSH key for this server"
            keys={targetRootKeys}
            errors={errors.target_ssh_key_id}
          />

          {isLoadingMainNode ? (
            <div className="flex items-center gap-2 text-grey text-sm">
              <LoaderIcon className="animate-spin flex-none" size={15} />
              <span>Loading main server keys...</span>
            </div>
          ) : mainNode ? (
            <RootSSHKeySelect
              name="main_ssh_key_id"
              label="Root SSH key for the main server"
              keys={mainRootKeys}
              errors={errors.main_ssh_key_id}
            />
          ) : (
            <Alert variant="destructive">
              <AlertCircleIcon className="size-4" />
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>
                Could not find the main server of the cluster.
              </AlertDescription>
            </Alert>
          )}
        </fetcher.Form>

        <DialogFooter className="-mx-6 px-6">
          <div className="flex items-center gap-4 w-full">
            <SubmitButton
              isPending={isPending}
              form="provision-swarm-node-form"
              className="inline-flex gap-1 items-center"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin flex-none" size={15} />
                  <span>Provisioning...</span>
                </>
              ) : (
                <span>Provision</span>
              )}
            </SubmitButton>
            <Button
              variant="outline"
              type="button"
              disabled={isPending}
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

type CancelSwarmNodeProvisionFormProps = {
  node: FullSwarmNode;
};

function CancelSwarmNodeProvisionForm({
  node
}: CancelSwarmNodeProvisionFormProps) {
  const fetcher = useFetcher<typeof cancelProvisionClientAction>();
  const isPending = fetcher.state !== "idle";

  return (
    <fetcher.Form
      method="post"
      action={href("/admin/servers/:serverId/cancel-provision", {
        serverId: node.id
      })}
    >
      <SubmitButton
        isPending={isPending}
        size="sm"
        variant="destructive"
        className={cn(
          "inline-flex gap-1 items-center",
          isPending && "opacity-80"
        )}
      >
        {isPending ? (
          <>
            <LoaderIcon className="animate-spin flex-none" size={15} />
            <span>Cancelling...</span>
          </>
        ) : (
          <span>Cancel provisioning</span>
        )}
      </SubmitButton>
    </fetcher.Form>
  );
}
