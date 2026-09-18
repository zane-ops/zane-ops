import { useQuery } from "@tanstack/react-query";
import {
  AtSignIcon,
  BoxIcon,
  BrainIcon,
  CableIcon,
  CpuIcon,
  FlameIcon,
  GlobeIcon,
  GlobeLockIcon,
  InfoIcon,
  KeyRoundIcon,
  MemoryStickIcon,
  MicrochipIcon,
  PackageIcon,
  PickaxeIcon,
  PlusIcon,
  WrenchIcon
} from "lucide-react";
import type { SwarmNode } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { DockerHubLogo } from "~/components/docker-hub-logo";
import { SSHKeyCard } from "~/components/ssh-key-card";
import { Button } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { swarmQueries } from "~/lib/queries";
import { cn, formatStorageValue, metaTitle } from "~/lib/utils";
import type { Route } from "./+types/swarm-node-details";

export function meta() {
  return [metaTitle("Server Details")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function SwarmNodeDetailsPage({
  params,
  matches: {
    "3": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: node } = useQuery({
    ...swarmQueries.singleNode(params.serverId),
    initialData: loaderData.node
  });

  const memory =
    node.memory_bytes !== null ? formatStorageValue(node.memory_bytes) : null;

  return (
    <section className="flex flex-col gap-4">
      <h3 className="text-grey">Update the details of this workspace</h3>

      <div className="grid lg:grid-cols-12 gap-10 relative">
        <div className="lg:col-span-10 flex flex-col">
          <section id="details" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <InfoIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">Details</h2>

              <div className="w-full max-w-4xl">
                <div className="flex flex-col  gap-2 w-full">
                  <FieldSet
                    name="swarm_role"
                    className="flex flex-col gap-1.5 flex-1"
                  >
                    <FieldSetLabel>Docker Swarm Role</FieldSetLabel>
                    <div className="relative">
                      <FieldSetInput
                        disabled
                        className={cn(
                          "disabled:placeholder-shown:font-mono disabled:bg-muted",
                          "disabled:border-transparent disabled:opacity-100",
                          "disabled:text-transparent disabled:select-none"
                        )}
                      />
                      <span
                        className={cn(
                          "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                          "max-w-full min-w-0 overflow-auto pr-4"
                        )}
                      >
                        {node.role === "MANAGER" ? (
                          <BrainIcon className="text-grey size-4 flex-none mr-1" />
                        ) : (
                          <PickaxeIcon className="text-grey size-4 flex-none mr-1" />
                        )}
                        <span className="text-card-foreground">
                          {node.role}
                        </span>
                      </span>
                    </div>
                  </FieldSet>

                  <FieldSet
                    name="cluster_roles"
                    className="flex flex-col gap-1.5 flex-1"
                  >
                    <FieldSetLabel>ZaneOps Cluster Roles</FieldSetLabel>
                    <div className="flex items-center gap-1.5">
                      {node.is_app_server && (
                        <TooltipProvider>
                          <Tooltip delayDuration={0}>
                            <TooltipTrigger asChild>
                              <Code className="inline-flex items-center gap-1 px-1.5 cursor-help">
                                <PackageIcon className="size-4 flex-none" />
                                <span>App Server</span>
                                <InfoIcon className="size-3 flex-none" />
                              </Code>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-64">
                              <span className="dark:text-card-foreground text-grey">
                                App server:&nbsp;
                              </span>
                              your services can be deployed and run on this
                              server.
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                      {node.is_build_server && (
                        <TooltipProvider>
                          <Tooltip delayDuration={0}>
                            <TooltipTrigger asChild>
                              <Code className="inline-flex items-center gap-1 px-1.5 cursor-help">
                                <WrenchIcon className="size-4 flex-none" />
                                <span>Build Server</span>
                                <InfoIcon className="size-3 flex-none" />
                              </Code>
                            </TooltipTrigger>
                            <TooltipContent className="max-w-64">
                              <span className="dark:text-card-foreground text-grey">
                                Build server:&nbsp;
                              </span>
                              docker images for git services are built on this
                              server.
                            </TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                    </div>
                  </FieldSet>
                </div>
              </div>
            </div>
          </section>

          <section
            id="networking"
            className="flex gap-1 scroll-mt-24 max-w-4xl"
          >
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <CableIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>
            <div className="w-full flex flex-col gap-12 pt-1 pb-14">
              <div className="flex flex-col gap-6">
                <h2 className="text-lg text-grey">Networking</h2>

                <div className="w-full max-w-4xl">
                  <div className="flex flex-col  gap-2 w-full">
                    <FieldSet
                      name="hostname"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Docker Swarm Hostname</FieldSetLabel>
                      <div className="relative">
                        <FieldSetInput
                          disabled
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted",
                            "disabled:border-transparent disabled:opacity-100",
                            "disabled:text-transparent disabled:select-none"
                          )}
                        />
                        <span
                          className={cn(
                            "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                            "max-w-full min-w-0 overflow-auto pr-4"
                          )}
                        >
                          <AtSignIcon className="text-grey size-4 flex-none mr-1" />
                          {node.hostname ? (
                            <span className="text-card-foreground">
                              {node.hostname}
                            </span>
                          ) : (
                            <code className="text-grey italic">
                              {"<unknown>"}
                            </code>
                          )}

                          {node.hostname && (
                            <TooltipProvider>
                              <Tooltip delayDuration={0}>
                                <TooltipTrigger asChild>
                                  <CopyButton
                                    value={node.hostname}
                                    label={node.hostname}
                                    className="!opacity-100 ml-1.5"
                                  />
                                </TooltipTrigger>
                                <TooltipContent>Copy Hostname</TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </span>
                      </div>
                    </FieldSet>

                    <FieldSet
                      name="private_ip"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Private IP</FieldSetLabel>
                      <div className="relative">
                        <FieldSetInput
                          disabled
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted",
                            "disabled:border-transparent disabled:opacity-100",
                            "disabled:text-transparent disabled:select-none"
                          )}
                        />

                        <span
                          className={cn(
                            "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                            "max-w-full min-w-0 overflow-auto pr-4"
                          )}
                        >
                          <GlobeLockIcon className="text-grey size-4 flex-none mr-1" />
                          <span>{node.private_ip}</span>
                          <TooltipProvider>
                            <Tooltip delayDuration={0}>
                              <TooltipTrigger asChild>
                                <CopyButton
                                  value={node.private_ip}
                                  label={node.private_ip}
                                  className="!opacity-100 ml-1.5"
                                />
                              </TooltipTrigger>
                              <TooltipContent>Copy Private IP</TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </span>
                      </div>
                    </FieldSet>

                    <FieldSet
                      name="public_ip"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Public IP</FieldSetLabel>
                      <div className="relative">
                        <FieldSetInput
                          disabled
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted",
                            "disabled:border-transparent disabled:opacity-100",
                            "disabled:text-transparent disabled:select-none"
                          )}
                        />

                        <span
                          className={cn(
                            "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                            "max-w-full min-w-0 overflow-auto pr-4"
                          )}
                        >
                          <GlobeIcon className="text-grey size-4 flex-none mr-1" />
                          {node.public_ip ? (
                            <span>{node.public_ip}</span>
                          ) : (
                            <code className="text-grey italic">
                              {"<unknown>"}
                            </code>
                          )}
                          {node.public_ip && (
                            <TooltipProvider>
                              <Tooltip delayDuration={0}>
                                <TooltipTrigger asChild>
                                  <CopyButton
                                    value={node.public_ip}
                                    label={node.public_ip}
                                    className="!opacity-100 ml-1.5"
                                  />
                                </TooltipTrigger>
                                <TooltipContent>Copy Public IP</TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </span>
                      </div>
                    </FieldSet>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section id="hardware" className="flex gap-1 scroll-mt-24 max-w-4xl">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <MicrochipIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>
            <div className="w-full flex flex-col gap-12 pt-1 pb-14">
              <div className="flex flex-col gap-6">
                <h2 className="text-lg text-grey">Hardware</h2>

                <div className="w-full max-w-4xl">
                  <div className="flex flex-col  gap-2 w-full">
                    <FieldSet
                      name="cpus"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>CPUs</FieldSetLabel>
                      <div className="relative">
                        <FieldSetInput
                          disabled
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted",
                            "disabled:border-transparent disabled:opacity-100",
                            "disabled:text-transparent disabled:select-none"
                          )}
                        />
                        <span
                          className={cn(
                            "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                            "max-w-full min-w-0 overflow-auto pr-4"
                          )}
                        >
                          <CpuIcon className="text-grey size-4 flex-none mr-1" />
                          {node.cpus ? (
                            <span className="text-card-foreground">
                              {node.cpus}
                            </span>
                          ) : (
                            <code className="text-grey italic">
                              {"<unknown>"}
                            </code>
                          )}
                        </span>
                      </div>
                    </FieldSet>

                    <FieldSet
                      name="memory"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Memory</FieldSetLabel>
                      <div className="relative">
                        <FieldSetInput
                          disabled
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted",
                            "disabled:border-transparent disabled:opacity-100",
                            "disabled:text-transparent disabled:select-none"
                          )}
                        />

                        <span
                          className={cn(
                            "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                            "max-w-full min-w-0 overflow-auto pr-4"
                          )}
                        >
                          <MemoryStickIcon className="text-grey size-4 flex-none mr-1" />
                          {memory ? (
                            <span>{`${memory.value} ${memory.unit}`}</span>
                          ) : (
                            <code className="text-grey italic">
                              {"<unknown>"}
                            </code>
                          )}
                        </span>
                      </div>
                    </FieldSet>

                    <FieldSet
                      name="docker_version"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Docker Version</FieldSetLabel>
                      <div className="relative">
                        <FieldSetInput
                          disabled
                          className={cn(
                            "disabled:placeholder-shown:font-mono disabled:bg-muted",
                            "disabled:border-transparent disabled:opacity-100",
                            "disabled:text-transparent disabled:select-none"
                          )}
                        />

                        <span
                          className={cn(
                            "absolute inset-y-0 flex items-center left-3 text-sm whitespace-nowrap",
                            "max-w-full min-w-0 overflow-auto pr-4"
                          )}
                        >
                          <DockerHubLogo className="size-4 flex-none mr-1" />
                          {node.docker_version ? (
                            <span>v{node.docker_version}</span>
                          ) : (
                            <code className="text-grey italic">
                              {"<unknown>"}
                            </code>
                          )}
                        </span>
                      </div>
                    </FieldSet>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section id="ssh-keys" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <KeyRoundIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8 items-start">
              <h2 className="text-lg text-grey">SSH Keys</h2>

              {node.ssh_keys.length > 0 && (
                <>
                  <ul className="w-full">
                    {node.ssh_keys.map((ssh_key) => (
                      <li key={ssh_key.id} className="w-full">
                        <SSHKeyCard
                          serverId={node.id}
                          sshKey={ssh_key}
                          className="w-full"
                        />
                      </li>
                    ))}
                  </ul>
                  <Separator />
                </>
              )}

              <SSHKeyAddDialog />
            </div>
          </section>

          <section id="danger" className="flex gap-1 scroll-mt-20">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-red-500">
                <FlameIcon size={15} className="flex-none text-red-500" />
              </div>
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-14">
              <h2 className="text-lg text-red-400">Danger Zone</h2>
              <div className="flex flex-col gap-4 items-start max-w-4xl w-full rounded-md border border-border py-4">
                <div className="flex md:flex-row gap-4 justify-between items-center w-full px-4">
                  <div className="flex flex-col gap-1">
                    <h3 className="text-lg font-medium">
                      Remove Server from cluster
                    </h3>
                    <p>
                      Drain all services from this server and remove it from the
                      cluster
                    </p>
                  </div>
                  <SwarmNodeRemoveForm {...node} />
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function SSHKeyAddDialog() {
  return (
    <Button variant="secondary">
      <PlusIcon className="size-4 flex-none" />
      Add new key
    </Button>
  );
}

function SwarmNodeRemoveForm(node: SwarmNode) {
  return (
    <TooltipProvider>
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <Button
            variant="destructive"
            className={cn(
              "destructive-outline gap-2",
              node.is_initial_install_server && "opacity-50"
            )}
            onClick={(e) => {
              if (node.is_initial_install_server) {
                e.preventDefault();
              }
            }}
          >
            Remove Server
          </Button>
        </TooltipTrigger>
        {node.is_initial_install_server && (
          <TooltipContent className="max-w-56 text-pretty">
            You cannot remove the main ZaneOps server from the cluster.
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  );
}
