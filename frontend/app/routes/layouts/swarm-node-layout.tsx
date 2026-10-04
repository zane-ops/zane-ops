import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  AlertCircleIcon,
  CheckIcon,
  ChevronDownIcon,
  CrownIcon,
  HammerIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  SearchIcon,
  ServerCogIcon,
  ServerIcon,
  SettingsIcon,
  SquareChartGanttIcon,
  TerminalIcon
} from "lucide-react";
import * as React from "react";
import { Outlet, href, useFetcher } from "react-router";
import type { SSHKey, SwarmNode } from "~/api/types";
import { Code } from "~/components/code";
import { HorizontalNavLink } from "~/components/horizontal-nav-link";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandItem,
  CommandList
} from "~/components/ui/command";
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
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
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

  return (
    <>
      <title>{title}</title>
      <div className="flex flex-col gap-4">
        <section className="flex items-center gap-3">
          <h2 className="text-2xl flex items-center gap-2">
            <ServerIcon className="size-6 text-grey" />
            <div className="inline-flex gap-0.5 font-medium items-center group-hover:underline">
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
  node: SwarmNode;
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
        <Button variant="secondary" className="gap-1.5" size="sm">
          <HammerIcon className="size-4 flex-none" />
          Provision node
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0 max-w-xl">
        <DialogHeader className="pb-4">
          <DialogTitle>Provision this server</DialogTitle>
          <DialogDescription>
            ZaneOps will connect to both this server and the main server as{" "}
            <Code>root</Code> to install Docker and join this server to the
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

type RootSSHKeySelectProps = {
  name: string;
  label: string;
  keys: SSHKey[];
  errors?: string[];
};

function RootSSHKeySelect({
  name,
  label,
  keys,
  errors
}: RootSSHKeySelectProps) {
  const [isPopoverOpen, setPopoverOpen] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [selectedKeyId, setSelectedKeyId] = React.useState<number | null>(null);

  const selectedKey =
    keys.find((key) => key.id === selectedKeyId) ?? keys[0] ?? null;

  const filteredKeys = keys.filter((key) =>
    `${key.name} ${key.fingerprint ?? ""}`
      .toLowerCase()
      .includes(query.trim().toLowerCase())
  );

  const errorId = `${name}-error`;

  return (
    <fieldset className="flex flex-col gap-1.5 flex-1">
      <label htmlFor={name}>{label}</label>

      {selectedKey && (
        <input type="hidden" name={name} value={selectedKey.id} />
      )}

      <Popover open={isPopoverOpen} onOpenChange={setPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            id={name}
            variant="outline"
            type="button"
            className="justify-between"
            aria-describedby={errorId}
            aria-invalid={!!errors}
          >
            {selectedKey ? (
              <span className="inline-flex items-center gap-2 min-w-0">
                <KeyRoundIcon className="size-4 flex-none text-grey" />
                <span>{selectedKey.name}</span>
                <span className="text-grey text-xs font-mono truncate">
                  {selectedKey.fingerprint?.toLowerCase()}
                </span>
              </span>
            ) : (
              <span className="text-sm">Select a SSH key</span>
            )}
            <ChevronDownIcon className="size-4 flex-none" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className={cn(
            "!w-(--radix-popover-trigger-width) p-0 z-999 shadow-md rounded-lg",
            "[&_[data-slot='command-list-wrapper']_*]:static",
            "[&_[data-slot='command-input-wrapper']]:px-2"
          )}
          align="center"
        >
          <Command shouldFilter={false} className="w-full">
            <div className="flex px-3 py-3.5 items-center gap-1">
              <SearchIcon className="size-4 flex-none text-grey" />
              <CommandPrimitive.Input
                placeholder="Search SSH keys"
                className="text-sm bg-inherit focus-visible:outline-hidden px-2 w-full"
                onValueChange={setQuery}
                value={query}
              />
            </div>
            <hr className="w-full border-border" />
            <CommandList className="flex flex-col gap-2 min-w-32 md:min-w-42 w-full bg-transparent border-none">
              <CommandEmpty>No root SSH keys found.</CommandEmpty>

              {filteredKeys.map((key) => {
                const isSelected = key.id === selectedKey?.id;

                return (
                  <CommandItem
                    key={key.id}
                    value={key.id.toString()}
                    onSelect={() => {
                      setSelectedKeyId(key.id);
                      setQuery("");
                      setPopoverOpen(false);
                    }}
                    className="cursor-pointer flex gap-1.5"
                  >
                    <div className="flex items-center justify-between w-full gap-4 min-w-0">
                      <span className="inline-flex items-center gap-2 min-w-0">
                        <KeyRoundIcon className="size-4 flex-none text-grey" />
                        <span>{key.name}</span>
                        <span className="text-grey text-xs font-mono truncate">
                          {key.fingerprint?.toLowerCase()}
                        </span>
                      </span>

                      <span className="flex size-4 items-center justify-center flex-none py-2.5">
                        {isSelected && (
                          <CheckIcon className="size-4 text-grey" />
                        )}
                      </span>
                    </div>
                  </CommandItem>
                );
              })}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {errors && (
        <span id={errorId} className="text-red-500 text-sm">
          {errors}
        </span>
      )}
    </fieldset>
  );
}
