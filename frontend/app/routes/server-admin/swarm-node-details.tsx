import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  AtSignIcon,
  BrainIcon,
  CableIcon,
  CheckIcon,
  ChevronRightIcon,
  CogIcon,
  CpuIcon,
  EthernetPortIcon,
  FlameIcon,
  GlobeLockIcon,
  HashIcon,
  InfoIcon,
  KeyRoundIcon,
  LoaderIcon,
  MemoryStickIcon,
  MicrochipIcon,
  PackageIcon,
  PencilLineIcon,
  PickaxeIcon,
  PlusIcon,
  ServerOffIcon,
  Trash2Icon,
  WrenchIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { Link, href, redirect, useFetcher } from "react-router";
import { toast } from "sonner";
import { type RequestInput, apiClient } from "~/api/client";
import type { FullSwarmNode, SwarmNode } from "~/api/types";
import type { components } from "~/api/v1";
import { Code } from "~/components/code";
import { CopyButton } from "~/components/copy-button";
import {
  DeleteConfirmationDialog,
  SimpleConfirmationDialog
} from "~/components/delete-confirmation-dialog";
import { DockerHubLogo } from "~/components/docker-hub-logo";
import { RootSSHKeySelect } from "~/components/root-ssh-key-select";
import { SSHKeyCard } from "~/components/ssh-key-card";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "~/components/ui/dialog";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetErrors,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { Separator } from "~/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { createDevLogger } from "~/lib/logger";
import { swarmQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import {
  type ErrorResponseFromAPI,
  cn,
  formatStorageValue,
  getCsrfTokenHeader,
  getFormErrorsFromResponseData,
  metaTitle
} from "~/lib/utils";
import type { Route } from "./+types/swarm-node-details";
import type { clientAction as createSSHKeyClientAction } from "./create-swarm-node-ssh-key";

export function meta() {
  return [metaTitle("Server Details")] satisfies ReturnType<Route.MetaFunction>;
}

const logger = createDevLogger(import.meta.url);

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
      <h3 className="text-grey">Update the details of this server</h3>

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

              <SwarmNodeDetailsForm node={node} />
            </div>
          </section>

          <section id="hardware" className="flex gap-1 scroll-mt-24 max-w-4xl">
            <div className="w-16 hidden md:flex flex-col items-center">
              <div className="flex rounded-full size-10 flex-none items-center justify-center p-1 border-2 border-grey/50">
                <MicrochipIcon size={15} className="flex-none text-grey" />
              </div>
              <div className="h-full border border-grey/50"></div>
            </div>
            <div className="w-full flex flex-col gap-12 pt-1 pb-8">
              <div className="flex flex-col gap-6">
                <h2 className="text-lg text-grey">Hardware</h2>

                <div className="w-full max-w-4xl">
                  <div className="flex flex-col  gap-2 w-full">
                    <FieldSet
                      name="architecture"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Architecture</FieldSetLabel>
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
                          <CogIcon className="text-grey size-4 flex-none mr-1" />
                          {node.architecture ? (
                            <span className="text-card-foreground">
                              {node.architecture}
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
            <div className="w-full flex flex-col gap-12 pt-1 pb-8">
              <div className="flex flex-col gap-6">
                <h2 className="text-lg text-grey">Networking</h2>

                <div className="w-full max-w-4xl">
                  <div className="flex flex-col  gap-2 w-full">
                    <FieldSet
                      name="swarm_node_id"
                      className="flex flex-col gap-1.5 flex-1"
                    >
                      <FieldSetLabel>Docker Swarm Node ID</FieldSetLabel>
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
                          <HashIcon className="text-grey size-4 flex-none mr-1" />
                          {node.swarm_node_id ? (
                            <span className="text-card-foreground">
                              {node.swarm_node_id}
                            </span>
                          ) : (
                            <code className="text-grey italic">
                              {"<unknown>"}
                            </code>
                          )}

                          {node.swarm_node_id && (
                            <TooltipProvider>
                              <Tooltip delayDuration={0}>
                                <TooltipTrigger asChild>
                                  <CopyButton
                                    value={node.swarm_node_id}
                                    label={node.swarm_node_id}
                                    className="!opacity-100 ml-1.5"
                                  />
                                </TooltipTrigger>
                                <TooltipContent>Copy Node ID</TooltipContent>
                              </Tooltip>
                            </TooltipProvider>
                          )}
                        </span>
                      </div>
                    </FieldSet>

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

                    <SwarmNodeSSHPortForm node={node} />
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
              {!node.is_initial_install_server && (
                <div className="h-full border border-grey/50"></div>
              )}
            </div>

            <div className="w-full flex flex-col gap-5 pt-1 pb-8 items-start">
              <h2 className="text-lg text-grey">SSH Keys</h2>

              {node.ssh_keys.length > 0 && (
                <>
                  <ul className="w-full flex flex-col gap-2">
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

              <SSHKeyAddDialog serverId={node.id} />
            </div>
          </section>

          {!node.is_initial_install_server && (
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
                        Deprovision server
                      </h3>
                      <p>
                        Move all services running on this server to other
                        servers, then remove it from the cluster.
                      </p>
                    </div>
                    <SwarmDeprovisionForm {...node} />
                  </div>
                  <Separator />

                  <div className="flex md:flex-row gap-4 justify-between items-center w-full px-4">
                    <div className="flex flex-col gap-1">
                      <h3 className="text-lg font-medium">Delete server</h3>
                      <p>
                        Delete this server and its SSH keys from ZaneOps.
                        Nothing is uninstalled on the server itself.
                      </p>
                    </div>
                    <SwarmNodeDeleteForm {...node} />
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}

type SSHKeyAddDialogProps = {
  serverId: string;
};

function SSHKeyAddDialog({ serverId }: SSHKeyAddDialogProps) {
  const fetcher = useFetcher<typeof createSSHKeyClientAction>();
  const [open, setOpen] = React.useState(false);
  const [data, setData] = React.useState(fetcher.data);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const isPending = fetcher.state !== "idle";

  const errors = getFormErrorsFromResponseData(data?.errors);
  const createdKey = data?.data ?? null;

  React.useEffect(() => {
    setData(fetcher.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher.state, fetcher.data]);

  React.useEffect(() => {
    const key = Object.keys(errors ?? {})[0];
    const field = formRef.current?.elements.namedItem(key) as HTMLInputElement;
    field?.focus();
  }, [errors]);

  const close = React.useCallback(() => {
    setOpen(false);
    setData(undefined);
  }, []);

  const commands = createdKey
    ? [
        "mkdir -p $HOME/.ssh",
        "touch $HOME/.ssh/authorized_keys",
        "chmod 600 $HOME/.ssh/authorized_keys",
        'echo "" >> $HOME/.ssh/authorized_keys',
        `echo '${createdKey.public_key}' >> $HOME/.ssh/authorized_keys`
      ]
    : [];

  return (
    <Dialog
      open={open}
      onOpenChange={(open) => {
        if (isPending) return;
        setOpen(open);
        if (!open) close();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="secondary">
          <PlusIcon className="size-4 flex-none" />
          Add new key
        </Button>
      </DialogTrigger>

      <DialogContent className="gap-0 max-w-xl">
        <DialogHeader className="pb-4">
          <DialogTitle>
            {createdKey ? (
              <>
                SSH key&nbsp;
                <span className="text-grey">
                  &ldquo;{createdKey.name}&rdquo;
                </span>
                &nbsp;created
              </>
            ) : (
              <>Add a new SSH key</>
            )}
          </DialogTitle>

          {createdKey ? (
            <Alert variant="success" className="mt-5">
              <CheckIcon className="size-4" />
              <AlertTitle>Key created</AlertTitle>
              <AlertDescription>
                To allow login with this key, add its public key to the{" "}
                <Code>~/.ssh/authorized_keys</Code> file of{" "}
                <span className="font-medium">{createdKey.user}</span> on this
                server using these commands:
              </AlertDescription>
            </Alert>
          ) : (
            errors.non_field_errors && (
              <Alert variant="destructive" className="mt-5">
                <AlertCircleIcon className="size-4" />
                <AlertTitle>Error</AlertTitle>
                <AlertDescription>{errors.non_field_errors}</AlertDescription>
              </Alert>
            )
          )}
        </DialogHeader>

        {createdKey ? (
          <div className="relative mb-5 w-full min-w-0">
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <CopyButton
                    value={commands.join("\n")}
                    label="Copy commands"
                    className="opacity-100! absolute top-2 right-2 font-sans"
                  />
                </TooltipTrigger>
                <TooltipContent>Copy commands</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <pre
              className={cn(
                "text-sm font-mono",
                "rounded-md",
                "overflow-x-auto overflow-y-clip bg-muted/25 dark:bg-neutral-950",
                "max-w-full p-4 w-full min-w-0"
              )}
            >
              {commands.map((cmd, index) => (
                <div key={index}>
                  <span className="text-primary select-none">$</span>&nbsp;
                  <span>{cmd}</span>
                  &nbsp;&nbsp;
                </div>
              ))}
            </pre>
          </div>
        ) : (
          <fetcher.Form
            ref={formRef}
            method="post"
            action={href("/admin/servers/:serverId/ssh-keys", { serverId })}
            id="create-ssh-key-form"
            className="flex flex-col gap-4 mb-5"
          >
            <FieldSet
              errors={errors.user}
              name="user"
              required
              className="flex flex-col gap-1"
            >
              <FieldSetLabel className="flex items-center gap-0.5">
                Username
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} className="text-grey" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-64 dark:bg-card">
                      User to login as on this server
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <FieldSetInput
                autoComplete="off"
                autoFocus
                placeholder="ex: root"
                defaultValue={data?.userData?.user}
              />
            </FieldSet>
            <FieldSet
              errors={errors.name}
              name="name"
              required
              className="flex flex-col gap-1"
            >
              <FieldSetLabel>Name</FieldSetLabel>
              <FieldSetInput
                placeholder="ex: my ssh key"
                defaultValue={data?.userData?.name}
              />
            </FieldSet>
          </fetcher.Form>
        )}

        <DialogFooter className="-mx-6 px-6">
          <div className="flex items-center gap-4 w-full">
            {createdKey ? (
              <>
                <Button asChild>
                  <Link
                    to={{
                      pathname: href("/admin/servers/:serverId/console", {
                        serverId
                      }),
                      search: `?ssh_key_id=${createdKey.id}`
                    }}
                    className="items-center gap-2"
                  >
                    Use this key
                    <ChevronRightIcon className="size-4 flex-none" />
                  </Link>
                </Button>
                <Button variant="outline" type="button" onClick={close}>
                  Close
                </Button>
              </>
            ) : (
              <>
                <SubmitButton
                  isPending={isPending}
                  form="create-ssh-key-form"
                  className="inline-flex gap-1 items-center"
                >
                  {isPending ? (
                    <>
                      <LoaderIcon
                        className="animate-spin flex-none"
                        size={15}
                      />
                      <span>Adding key...</span>
                    </>
                  ) : (
                    <span>Add SSH key</span>
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
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SwarmNodeDeleteForm(node: FullSwarmNode) {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const isMemberOfCluster = ![
    "CREATED",
    "FAILED",
    "REMOVED",
    "PROVISIONING"
  ].includes(node.status);
  const nodeName = node.hostname ?? node.private_ip;

  return isMemberOfCluster ? (
    <TooltipProvider>
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <Button
            variant="destructive"
            className="destructive-outline gap-2 opacity-50"
            onClick={(e) => e.preventDefault()}
          >
            <Trash2Icon size={15} className="flex-none" />
            Delete Server
          </Button>
        </TooltipTrigger>
        <TooltipContent className="max-w-56 text-pretty">
          This server is still part of the cluster. Deprovision it before
          deleting it.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ) : (
    <DeleteConfirmationDialog
      fetcher={fetcher}
      title={
        <>
          Delete the server&nbsp;
          <span className="text-grey">&ldquo;{nodeName}&rdquo;</span>?
        </>
      }
      message={
        <p>
          This server and all its SSH keys will be permanently deleted from
          ZaneOps. This action cannot be undone.
        </p>
      }
      confirmationValue={nodeName}
      confirmationFieldName="server_name"
      form={
        <fetcher.Form method="post">
          <FieldSet name="server_name" errors={errors.server_name}>
            <FieldSetInput />
          </FieldSet>
          <input type="hidden" name="intent" value="delete-server" />
        </fetcher.Form>
      }
      trigger={
        <DialogTrigger asChild>
          <Button variant="destructive" className="destructive-outline gap-2">
            <Trash2Icon size={15} className="flex-none" />
            Delete Server
          </Button>
        </DialogTrigger>
      }
    />
  );
}

function SwarmDeprovisionForm(node: FullSwarmNode) {
  const fetcher = useFetcher<typeof clientAction>();
  const errors = getFormErrorsFromResponseData(fetcher.data?.errors);
  const isNotMemberOfClusterYet = [
    "CREATED",
    "FAILED",
    "REMOVED",
    "PROVISIONING"
  ].includes(node.status);

  const { data: mainNode, isLoading: isLoadingMainNode } = useQuery({
    ...swarmQueries.mainNode,
    enabled: !isNotMemberOfClusterYet
  });

  const targetRootKeys = node.ssh_keys.filter((key) => key.user === "root");
  const mainRootKeys = (mainNode?.ssh_keys ?? []).filter(
    (key) => key.user === "root"
  );

  return isNotMemberOfClusterYet ? (
    <TooltipProvider>
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>
          <Button
            variant="warning"
            className="destructive-outline gap-2 opacity-50"
            onClick={(e) => e.preventDefault()}
          >
            <ServerOffIcon size={15} className="flex-none" />
            Deprovision Server
          </Button>
        </TooltipTrigger>
        <TooltipContent className="max-w-56 text-pretty">
          This server is not part of the cluster yet, so there is nothing to
          deprovision.
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  ) : (
    <SimpleConfirmationDialog
      fetcher={fetcher}
      variant="warning"
      className="max-w-xl"
      title={
        <>
          Deprovision the server&nbsp;
          <span className="text-grey">
            &ldquo;{node.hostname ?? node.private_ip}&rdquo;
          </span>
          ?
        </>
      }
      message={
        <p>
          All services running on this server will be moved to other servers,
          then the server will leave the cluster. ZaneOps will need to connect
          to both this server and the main server as <Code>root</Code> to
          proceed.
        </p>
      }
      confirmText="Deprovision"
      pendingText="Deprovisioning..."
      form={
        <fetcher.Form method="post" className="flex flex-col gap-4 mb-5">
          <input type="hidden" name="intent" value="deprovision-server" />
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
      }
      trigger={
        <DialogTrigger asChild>
          <Button variant="warning" className="destructive-outline gap-2">
            <ServerOffIcon size={15} className="flex-none" />
            Deprovision Server
          </Button>
        </DialogTrigger>
      }
    />
  );
}

type SwarmNodeFormProps = {
  node: SwarmNode;
};

function SwarmNodeDetailsForm({ node }: SwarmNodeFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);
  const errors = getFormErrorsFromResponseData(data?.errors);

  const [swarmRole, setSwarmRole] = React.useState(node.swarm_role);
  const [clusterRoles, setClusterRoles] = React.useState(node.cluster_roles);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      setIsEditing(false);
    }
  }, [fetcher.state, fetcher.data]);

  const toggleClusterRole = (
    role: SwarmNode["cluster_roles"][number],
    checked: boolean
  ) => {
    setClusterRoles((roles) =>
      checked ? [...roles, role] : roles.filter((r) => r !== role)
    );
  };

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form method="post" className="flex flex-col gap-4 w-full">
        {errors.non_field_errors && (
          <Alert variant="destructive">
            <AlertCircleIcon className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{errors.non_field_errors}</AlertDescription>
          </Alert>
        )}

        <FieldSet
          errors={errors.swarm_role}
          name="swarm_role"
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel htmlFor="swarm_role">Docker Swarm Role</FieldSetLabel>
          <FieldSetSelect
            name="swarm_role"
            value={swarmRole}
            disabled={!isEditing || node.is_initial_install_server}
            onValueChange={(value) =>
              setSwarmRole(value as SwarmNode["swarm_role"])
            }
          >
            <SelectTrigger
              id="swarm_role"
              ref={SelectTriggerRef}
              className={cn(
                "[&_[data-item]]:flex-row [&_[data-item]]:gap-2",
                "[&_[data-item]_[data-description]]:hidden",
                "disabled:bg-muted disabled:border-transparent disabled:opacity-100"
              )}
            >
              <SelectValue placeholder="Select a swarm role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                value="WORKER"
                className="flex items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-1"
              >
                <div className="inline-flex items-start gap-2">
                  <PickaxeIcon className="size-4 flex-none relative top-1" />
                  <div className="flex flex-col" data-item>
                    <span>Worker</span>
                    <span className="text-muted-foreground" data-description>
                      Only runs workloads assigned by the managers
                    </span>
                  </div>
                </div>
              </SelectItem>
              <SelectItem
                value="MANAGER"
                className="flex items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-1"
              >
                <div className="inline-flex items-start gap-2">
                  <BrainIcon className="size-4 flex-none relative top-1" />
                  <div className="flex flex-col" data-item>
                    <span>Manager</span>
                    <span className="text-muted-foreground" data-description>
                      Runs workloads and takes part in managing the Docker swarm
                      cluster state
                    </span>
                  </div>
                </div>
              </SelectItem>
            </SelectContent>
          </FieldSetSelect>
        </FieldSet>

        <div className="flex flex-col gap-2">
          <span>ZaneOps Cluster Roles</span>

          {errors.cluster_roles && (
            <FieldSet
              errors={errors.cluster_roles}
              className="flex flex-col gap-1"
            >
              <FieldSetErrors />
            </FieldSet>
          )}

          <FieldSet
            name="cluster_roles"
            className="flex-1 inline-flex gap-2 flex-col"
          >
            <div className="inline-flex gap-2 items-start">
              <FieldSetCheckbox
                value="APP_SERVER"
                disabled={!isEditing}
                checked={clusterRoles.includes("APP_SERVER")}
                onCheckedChange={(checked) =>
                  toggleClusterRole("APP_SERVER", checked === true)
                }
                className="relative top-1 disabled:opacity-60"
              />

              <div className="flex flex-col gap-0.5">
                <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                  <PackageIcon className="size-4 flex-none" />
                  App Server
                </FieldSetLabel>

                <small className="text-grey text-sm">
                  Your services can be deployed and run on this server.
                </small>
              </div>
            </div>
          </FieldSet>

          <FieldSet
            name="cluster_roles"
            className="flex-1 inline-flex gap-2 flex-col"
          >
            <div className="inline-flex gap-2 items-start">
              <FieldSetCheckbox
                value="BUILD_SERVER"
                disabled={!isEditing}
                checked={clusterRoles.includes("BUILD_SERVER")}
                onCheckedChange={(checked) =>
                  toggleClusterRole("BUILD_SERVER", checked === true)
                }
                className="relative top-1 disabled:opacity-60"
              />

              <div className="flex flex-col gap-0.5">
                <FieldSetLabel className="inline-flex gap-1 items-center dark:text-card-foreground">
                  <WrenchIcon className="size-4 flex-none" />
                  Build Server
                </FieldSetLabel>

                <small className="text-grey text-sm">
                  Docker images for git services can be built on this server.
                </small>
              </div>
            </div>
          </FieldSet>
        </div>

        <div className="flex gap-4">
          {isEditing && (
            <SubmitButton
              isPending={isPending}
              variant="secondary"
              className="self-start"
              name="intent"
              value="update-details"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span>Updating...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span>Update</span>
                </>
              )}
            </SubmitButton>
          )}
          <Button
            variant="outline"
            type="reset"
            disabled={isPending}
            onClick={() => {
              const newIsEditing = !isEditing;
              flushSync(() => {
                setIsEditing(newIsEditing);
                setSwarmRole(node.swarm_role);
                setClusterRoles(node.cluster_roles);
              });
              if (newIsEditing) {
                SelectTriggerRef.current?.focus();
              }
              setData(undefined);
            }}
            className="bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
          >
            {!isEditing ? (
              <>
                <span>Edit</span>
                <PencilLineIcon size={15} className="flex-none" />
              </>
            ) : (
              <>
                <XIcon size={15} className="flex-none" />
                <span>Cancel</span>
              </>
            )}
          </Button>
        </div>
      </fetcher.Form>
    </div>
  );
}

function SwarmNodeSSHPortForm({ node }: SwarmNodeFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data && !fetcher.data.errors) {
      setIsEditing(false);
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <fetcher.Form
      method="post"
      className="flex flex-col md:flex-row gap-2 w-full"
    >
      <FieldSet
        name="ssh_port"
        errors={errors.non_field_errors || errors.ssh_port}
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>SSH Port</FieldSetLabel>
        <div className="relative">
          <FieldSetInput
            ref={inputRef}
            placeholder="ex: 22"
            defaultValue={node.ssh_port}
            disabled={!isEditing}
            className={cn(
              "disabled:bg-muted",
              "disabled:border-transparent disabled:opacity-100",
              !isEditing && "pl-8"
            )}
          />
          {!isEditing && (
            <EthernetPortIcon className="text-grey size-4 flex-none absolute left-3 top-1/2 -translate-y-1/2" />
          )}

          {!isEditing && (
            <Button
              variant="outline"
              onClick={() => {
                flushSync(() => {
                  setIsEditing(true);
                });
                inputRef.current?.focus();
              }}
              className={cn(
                "absolute inset-y-0 right-0 text-sm py-0 border-0",
                "bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
              )}
            >
              <span>Edit</span>
              <PencilLineIcon size={15} />
            </Button>
          )}
        </div>
      </FieldSet>

      {isEditing && (
        <div className="flex gap-2 md:relative top-8">
          <SubmitButton
            isPending={isPending}
            variant="outline"
            className="bg-inherit"
            name="intent"
            value="update-ssh-port"
          >
            {isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span className="sr-only">Updating SSH port...</span>
              </>
            ) : (
              <>
                <CheckIcon size={15} className="flex-none" />
                <span className="sr-only">Update SSH port</span>
              </>
            )}
          </SubmitButton>
          <Button
            onClick={(ev) => {
              ev.currentTarget.form?.reset();
              setIsEditing(false);
              setData(undefined);
            }}
            variant="outline"
            className="bg-inherit"
            type="reset"
          >
            <XIcon size={15} className="flex-none" />
            <span className="sr-only">Cancel</span>
          </Button>
        </div>
      )}
    </fetcher.Form>
  );
}

export async function clientAction({
  request,
  params
}: Route.ClientActionArgs) {
  const formData = await request.formData();
  const intent = formData.get("intent")?.toString();

  switch (intent) {
    case "update-ssh-port": {
      return updateSSHPort(params.serverId, formData);
    }
    case "delete-server": {
      return deleteServer(params.serverId, formData);
    }
    case "deprovision-server": {
      return deprovisionServer(params.serverId, formData);
    }
    case "update-details": {
      // TODO: call the node update endpoint once it is implemented
      const userData = {
        swarm_role: formData
          .get("swarm_role")
          ?.toString() as SwarmNode["swarm_role"],
        cluster_roles: formData
          .getAll("cluster_roles")
          .map((role) => role.toString()) as SwarmNode["cluster_roles"]
      };
      logger.info({ intent, userData });
      return {
        errors: undefined as
          | components["schemas"]["SwarmNodesCreateErrorResponse400"]
          | undefined,
        data: undefined,
        userData
      };
    }
    default: {
      throw new Error(`Unexpected intent \`${intent}\``);
    }
  }
}

async function updateSSHPort(serverId: string, formData: FormData) {
  const queryClient = getQueryClient();

  const userData = {
    ssh_port: formData.get("ssh_port")?.toString() as unknown as number
  } satisfies RequestInput<"patch", "/api/swarm/nodes/{id}/">;

  const { error: errors, data } = await apiClient.PATCH(
    "/api/swarm/nodes/{id}/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: serverId }
      },
      body: userData
    }
  );

  if (errors) {
    return {
      errors,
      userData
    };
  }

  await queryClient.invalidateQueries(swarmQueries.singleNode(serverId));
  toast.success("Success", {
    description: "SSH port updated successfully",
    closeButton: true
  });
  return { data };
}

async function deleteServer(serverId: string, formData: FormData) {
  const queryClient = getQueryClient();
  const node = await queryClient.ensureQueryData(
    swarmQueries.singleNode(serverId)
  );
  const nodeName = node.hostname ?? node.private_ip;

  if (formData.get("server_name")?.toString().trim() !== nodeName) {
    return {
      errors: {
        type: "validation_error",
        errors: [
          {
            attr: "server_name",
            code: "invalid",
            detail: "The server name does not match"
          }
        ]
      } satisfies ErrorResponseFromAPI
    };
  }

  const { error: errors } = await apiClient.DELETE("/api/swarm/nodes/{id}/", {
    headers: {
      ...(await getCsrfTokenHeader())
    },
    params: {
      path: { id: serverId }
    }
  });

  if (errors) {
    return { errors };
  }

  queryClient.removeQueries(swarmQueries.singleNode(serverId));
  await queryClient.invalidateQueries({
    queryKey: swarmQueries.nodeList().queryKey.slice(0, 1)
  });

  toast.success("Success", {
    description: (
      <span>
        Server <strong>{nodeName}</strong> has been deleted.
      </span>
    ),
    closeButton: true
  });
  throw redirect(href("/admin/servers"));
}

async function deprovisionServer(serverId: string, formData: FormData) {
  const queryClient = getQueryClient();

  const userData = {
    target_ssh_key_id: Number(formData.get("target_ssh_key_id")),
    main_ssh_key_id: Number(formData.get("main_ssh_key_id"))
  } satisfies RequestInput<"put", "/api/swarm/nodes/{id}/deprovision/">;

  const { error: errors } = await apiClient.PUT(
    "/api/swarm/nodes/{id}/deprovision/",
    {
      headers: {
        ...(await getCsrfTokenHeader())
      },
      params: {
        path: { id: serverId }
      },
      body: userData
    }
  );

  if (errors) {
    return { errors, userData };
  }

  await queryClient.invalidateQueries({
    queryKey: swarmQueries.nodeList().queryKey.slice(0, 1)
  });

  toast.success("Success", {
    description: "Deprovisioning of the server has started",
    closeButton: true
  });
  throw redirect(
    href("/admin/servers/:serverId/deployment-logs", { serverId })
  );
}
