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
  PickaxeIcon,
  WrenchIcon
} from "lucide-react";
import type { SwarmNode } from "~/api/types";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import { DockerHubLogo } from "~/components/docker-hub-logo";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
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
                    <FieldSetLabel>Swarm Role</FieldSetLabel>
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
                              <Code className="inline-flex items-center gap-1 cursor-help">
                                <BoxIcon className="size-4 flex-none" />
                                <span>App Server</span>
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
                              <Code className="inline-flex items-center gap-1 cursor-help">
                                <WrenchIcon className="size-4 flex-none" />
                                <span>Build Server</span>
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
                      <FieldSetLabel>Swarm Hostname</FieldSetLabel>
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
                          <span className="text-card-foreground">
                            {node.hostname}
                          </span>
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
                          defaultValue={node.public_ip}
                          disabled
                          placeholder={"<empty>"}
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
                            <code className="text-grey">
                              {"[no public ip]"}
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
                          <span className="text-card-foreground">
                            {node.cpus}
                          </span>
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
                          <span>
                            {memory ? `${memory.value} ${memory.unit}` : "-"}
                          </span>
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
                            <code className="text-grey">{"[empty]"}</code>
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

            <div className="w-full flex flex-col gap-5 pt-1 pb-8">
              <h2 className="text-lg text-grey">SSH Keys</h2>

              {/* <WorkspaceDetailsForm name={workspace.name} /> */}
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
                  {/* <WorkspaceDeleteForm name={workspace.name} /> */}
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}

function SwarmNodeDetailsForm(props: SwarmNode) {
  return <></>;
}
