import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  LoaderIcon,
  PencilLineIcon,
  PinIcon,
  ServerIcon,
  ShuffleIcon,
  TriangleAlertIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import type { Service } from "~/api/types";
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
  getFormErrorsFromResponseData,
  hasMinRole
} from "~/lib/utils";
import { useCurrentWorkspaceMembership } from "~/lib/workspace-store";
import {
  type clientAction,
  useServiceQuery
} from "~/routes/services/settings/service-settings";

const logger = createDevLogger(import.meta.url);

export type ServiceFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

export function ServiceDeployStrategyForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const deployStrategySelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);
  const deployServerSelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const deployStrategyChange = (service.unapplied_changes ?? []).find(
    (change) => change.field === "deployment_strategy"
  ) as
    | {
        new_value: Pick<Service, "deployment_server" | "deployment_strategy">;
        id: string;
      }
    | undefined;

  const deploy_server_id =
    deployStrategyChange?.new_value.deployment_server?.id ??
    service.deployment_server?.id;

  const deploy_strategy =
    deployStrategyChange?.new_value.deployment_strategy ??
    service.deployment_strategy;

  const errors = getFormErrorsFromResponseData(data?.errors);

  const nodeListQuery = useQuery(swarmQueries.deployServerList);
  const servers = nodeListQuery.data ?? [];

  const [selectedDeployServerId, setSelectedDeployServerId] = React.useState(
    deploy_server_id ?? null
  );

  const [deploymentStrategy, setDeploymentStrategy] =
    React.useState(deploy_strategy);

  // a viewer cannot edit anything, and a field with a pending change is
  // locked until that change is applied or discarded
  const isNotEditable = deployStrategyChange !== undefined;

  const membership = useCurrentWorkspaceMembership();
  const isMember = hasMinRole(membership, "Member");

  React.useEffect(() => {
    if (errors.non_field_errors && errors.non_field_errors.length > 0) {
      const fullErrorMessages = errors.non_field_errors.join("\n");
      toast.error("Error", {
        description: fullErrorMessages,
        closeButton: true,
        onDismiss: () => {
          setData(undefined);
        }
      });
    }
  }, [errors]);

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsEditing(false);
        setSelectedDeployServerId(deploy_server_id ?? null);
        setDeploymentStrategy(deploy_strategy);
      }
    }
  }, [fetcher.state, fetcher.data, deploy_server_id, deploy_strategy]);

  return (
    <>
      <fetcher.Form method="post" className="flex flex-col gap-4" ref={formRef}>
        <legend className="text-lg">Deployment Strategy</legend>
        <p className="text-gray-400">
          Choose the server this service will be deployed on. If none is
          selected, ZaneOps uses the default server of the environment or
          project, or any available deploy server if no default is set.
        </p>

        <input type="hidden" name="change_field" value="deployment_strategy" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input
          type="hidden"
          name="change_id"
          value={deployStrategyChange?.id}
        />

        {isMember && (
          <Alert variant="warning">
            <TriangleAlertIcon size={15} />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              Changing servers might move this service to another node. Volumes
              are local to each node, so they will be recreated empty on the new
              server, which may result in data loss.
            </AlertDescription>
          </Alert>
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
          required
          errors={errors.new_value?.deployment_strategy}
          name="type"
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel htmlFor="deployment_strategy">
            Deployment strategy
          </FieldSetLabel>
          <FieldSetSelect
            name="deployment_strategy"
            disabled={isNotEditable}
            value={deploymentStrategy}
            defaultValue={deploymentStrategy}
            onValueChange={(value) =>
              setDeploymentStrategy(
                value as NonNullable<Service["deployment_strategy"]>
              )
            }
          >
            <SelectTrigger
              id="healthcheck_type"
              ref={deployStrategySelectTriggerRef}
              disabled={!isEditing || deployStrategyChange !== undefined}
              data-edited={
                deployStrategyChange !== undefined ? "true" : undefined
              }
              className={cn(
                "data-[edited=true]:bg-secondary/60 dark:data-[edited=true]:bg-secondary-foreground",
                "data-disabled:opacity-100 data-[edited=true]:border-transparent",
                "data-disabled:bg-muted data-[edited=false]:disabled:text-gray-400",
                "[&_[data-item]_.flex]:flex-row [&_[data-item]_.flex]:gap-1",
                "[&_[data-item]]:items-center [&_[data-item]_:first-child]:top-0"
              )}
            >
              <SelectValue placeholder="Select a type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                value="ANY_DEPLOY_SERVER"
                className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
              >
                <div data-item className="inline-flex items-start gap-2">
                  <ShuffleIcon className="relative flex-none size-4 top-1 text-grey" />
                  <div className="flex flex-col items-start gap-0">
                    <span>Any Deploy server</span>
                    <span className="text-grey">
                      Use the default server, or any available deploy server
                    </span>
                  </div>
                </div>
              </SelectItem>
              <SelectItem
                value="SPECIFIC_SERVER"
                className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
              >
                <div data-item className="inline-flex items-start gap-2">
                  <PinIcon className="relative flex-none size-4 top-1 text-grey" />
                  <div className="flex flex-col items-start gap-0">
                    <span>Specific Server</span>
                    <span className="text-grey">
                      Always deploy this service on the selected server
                    </span>
                  </div>
                </div>
              </SelectItem>
            </SelectContent>
          </FieldSetSelect>
        </FieldSet>

        {deploymentStrategy === "SPECIFIC_SERVER" && (
          <FieldSet
            required
            className="flex flex-col gap-1"
            name="deployment_server_id"
            errors={errors.new_value?.deployment_server_id}
          >
            <FieldSetLabel>Deployment Server</FieldSetLabel>

            <FieldSetSelect
              value={selectedDeployServerId ?? "<none>"}
              onValueChange={(value) => {
                logger.scope("ServiceDeployServerForm").info({ value });
                setSelectedDeployServerId(value);
              }}
            >
              <SelectTrigger
                ref={deployServerSelectTriggerRef}
                disabled={!isEditing || deployStrategyChange !== undefined}
                data-edited={
                  deployStrategyChange !== undefined ? "true" : undefined
                }
                className={cn(
                  "[&_[data-item]_.flex]:flex-row [&_[data-item]_.flex]:gap-1",
                  "[&_[data-item]]:items-center [&_[data-item]_:first-child]:top-0",
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100",
                  !selectedDeployServerId && "text-muted-foreground"
                )}
              >
                <SelectValue
                  placeholder="select a server"
                  className="text-grey"
                />
              </SelectTrigger>
              <SelectContent className="border border-border text-sm">
                <SelectItem
                  value="<none>"
                  disabled
                  className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
                >
                  <div data-item className="inline-flex items-center gap-2">
                    Select a server
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
        )}

        <div className="flex gap-4">
          {deployStrategyChange !== undefined ? (
            <>
              <SubmitButton
                isPending={isPending}
                variant="outline"
                name="intent"
                value="cancel-service-change"
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
                  value="request-service-change"
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
                    setDeploymentStrategy(deploy_strategy);
                  });
                  if (newIsEditing) {
                    deployStrategySelectTriggerRef.current?.focus();
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
    </>
  );
}
