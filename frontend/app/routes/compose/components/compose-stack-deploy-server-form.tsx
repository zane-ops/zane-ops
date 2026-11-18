import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  BanIcon,
  CheckIcon,
  LoaderIcon,
  PencilLineIcon,
  ServerIcon,
  ShuffleIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import type { ComposeStack } from "~/api/types";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import { createDevLogger } from "~/lib/logger";
import { swarmQueries } from "~/lib/queries";
import {
  cn,
  formatStorageValue,
  getFormErrorsFromResponseData
} from "~/lib/utils";
import type { clientAction } from "~/routes/compose/compose-stack-settings";

const logger = createDevLogger(import.meta.url);

export type ComposeStackDeployServerProps = {
  stack: ComposeStack;
  className?: string;
};

export function ComposeStackDeployServer({
  stack,
  className
}: ComposeStackDeployServerProps) {
  const fetcher = useFetcher<typeof clientAction>();

  const [isEditing, setIsEditing] = React.useState(false);

  const [data, setData] = React.useState(fetcher.data);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const deployServerChange = (stack?.unapplied_changes ?? []).find(
    (change) => change.field === "deploy_server"
  ) as {
    new_value: ComposeStack["deployment_server"];
    id: string;
  };

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = fetcher.state !== "idle";

  const deploy_server_id =
    deployServerChange?.new_value?.id ?? stack.deployment_server?.id;

  const [selectedDeployServerId, setSelectedDeployServerId] = React.useState(
    deploy_server_id ?? null
  );

  logger.info({
    "deployServerChange?.new_value.deployment_server":
      deployServerChange?.new_value,
    "stack.deployment_server": stack.deployment_server,
    deploy_server_id,
    selectedDeployServerId
  });

  const deployServerSelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const nodeListQuery = useQuery(swarmQueries.deployServerList);
  const servers = nodeListQuery.data ?? [];

  React.useEffect(() => {
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        formRef.current?.reset();
        setSelectedDeployServerId(deploy_server_id ?? null);
      }
    }
  }, [fetcher.data, fetcher.state, deploy_server_id]);
  return (
    <fetcher.Form
      method="post"
      className={cn("flex flex-col gap-4 max-w-4xl", className)}
      ref={formRef}
    >
      <input type="hidden" name="change_field" value="deploy_server" />
      <input type="hidden" name="change_type" value="UPDATE" />

      {deployServerChange !== undefined && (
        <input type="hidden" name="change_id" value={deployServerChange.id} />
      )}

      {errors.new_value?.non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {errors.new_value.non_field_errors}
          </AlertDescription>
        </Alert>
      )}

      <FieldSet
        className="flex flex-col gap-1"
        name="deployment_server_id"
        errors={errors.new_value?.deployment_server_id}
      >
        <FieldSetLabel className="text-base dark:text-card-foreground">
          Deployment Server
        </FieldSetLabel>
        <p className="text-gray-400 mt-2">
          Choose the server the services on this stack will be deployed on. If
          none is selected, ZaneOps uses the default server of the environment
          or project, or any available deploy server if no default is set.
        </p>

        <FieldSetSelect
          value={selectedDeployServerId ?? "<none>"}
          onValueChange={(value) => {
            logger.scope("ServiceDeployServerForm").info({ value });
            setSelectedDeployServerId(value);
          }}
        >
          <SelectTrigger
            ref={deployServerSelectTriggerRef}
            disabled={!isEditing || deployServerChange !== undefined}
            data-edited={deployServerChange !== undefined ? "true" : undefined}
            className={cn(
              "[&_[data-item]_.flex]:flex-row [&_[data-item]_.flex]:gap-1",
              "[&_[data-item]]:items-center [&_[data-item]_:first-child]:top-0",
              "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
              "data-[edited]:dark:disabled:bg-secondary-foreground",
              "disabled:border-transparent disabled:opacity-100",
              "mt-3"
            )}
          >
            <SelectValue placeholder="select a server" className="text-grey" />
          </SelectTrigger>
          <SelectContent className="border border-border text-sm">
            <SelectItem
              value="<none>"
              className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
            >
              <div data-item className="inline-flex items-start gap-2">
                <ShuffleIcon className="relative flex-none size-4 top-1" />
                <div className="flex flex-col items-start gap-0">
                  <span>Any Deploy Server</span>
                  <span className="text-grey">
                    Use the default server, or any available deploy server
                  </span>
                </div>
              </div>
            </SelectItem>
            {servers.map((server) => {
              const memory =
                server.memory_bytes !== null
                  ? formatStorageValue(server.memory_bytes)
                  : null;

              return (
                <SelectItem
                  value={server.id}
                  key={server.id}
                  className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
                >
                  <div data-item className="inline-flex items-start gap-2">
                    <ServerIcon className="relative flex-none size-4 top-1" />
                    <div className="flex flex-col items-start gap-0">
                      <span>{server.hostname}</span>
                      <span className="text-grey">
                        {memory && (
                          <span>
                            {memory.value} {memory.unit}&nbsp;
                          </span>
                        )}
                        {server.cpus && (
                          <span>&middot; {server.cpus} CPUs</span>
                        )}
                      </span>
                    </div>
                  </div>
                </SelectItem>
              );
            })}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>
      <div className="flex gap-4">
        {deployServerChange !== undefined ? (
          <>
            <SubmitButton
              isPending={isPending}
              variant="outline"
              name="intent"
              value="cancel-stack-change"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span>Discarding...</span>
                </>
              ) : (
                <>
                  <Undo2Icon size={15} className="flex-none" />
                  <span>Discard change</span>
                </>
              )}
            </SubmitButton>
          </>
        ) : (
          <>
            {isEditing && (
              <SubmitButton
                isPending={isPending}
                variant="secondary"
                className="self-start"
                name="intent"
                value="request-stack-change"
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
                  setSelectedDeployServerId(deploy_server_id ?? null);
                });
                if (newIsEditing) {
                  deployServerSelectTriggerRef.current?.focus();
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
          </>
        )}
      </div>
    </fetcher.Form>
  );
}
