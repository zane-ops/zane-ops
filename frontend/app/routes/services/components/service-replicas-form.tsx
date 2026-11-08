import {
  AlertCircleIcon,
  CheckIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import type { Service } from "~/api/types";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { createDevLogger } from "~/lib/logger";
import { cn, getFormErrorsFromResponseData, hasMinRole } from "~/lib/utils";
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

export function ServiceReplicasForm({
  project_slug,
  service_slug,
  env_slug
}: ServiceFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);

  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const replicasChange = (service.unapplied_changes ?? []).find(
    (change) => change.field === "replicas"
  ) as
    | {
        new_value: Pick<Service, "replicas">;
        id: string;
      }
    | undefined;

  const replicas = replicasChange?.new_value.replicas ?? service.replicas;

  const errors = getFormErrorsFromResponseData(data?.errors);

  const membership = useCurrentWorkspaceMembership();
  const isMember = hasMinRole(membership, "Member");
  // a viewer cannot edit anything, and a field with a pending change is
  // locked until that change is applied or discarded
  const isNotEditable = !isEditing || !isMember || replicasChange !== undefined;
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsEditing(false);
      }
    }
  }, [fetcher.state, fetcher.data]);

  return (
    <fetcher.Form
      method="post"
      className="flex flex-col gap-4 max-w-4xl"
      ref={formRef}
    >
      <input type="hidden" name="change_field" value="replicas" />
      <input type="hidden" name="change_type" value="UPDATE" />

      {replicasChange !== undefined && (
        <input type="hidden" name="change_id" value={replicasChange.id} />
      )}

      <div className="flex flex-col">
        <legend className="text-lg">Service Replicas</legend>
        <p className="text-gray-400">Number of instances to run in parallel</p>
      </div>
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
        name="replicas"
        errors={errors.new_value?.replicas}
        className="w-full flex flex-col md:flex-row gap-2"
      >
        <div className="flex flex-col gap-1.5 flex-1">
          <FieldSetLabel className="text-muted-foreground sr-only">
            Value
          </FieldSetLabel>
          <div className="relative h-full">
            <FieldSetInput
              placeholder="1"
              disabled={isNotEditable}
              data-edited={replicasChange !== undefined}
              ref={inputRef}
              className={cn(
                "disabled:placeholder-shown:font-mono data-[edited=true]:bg-secondary/60",
                "dark:data-[edited=true]:bg-secondary-foreground disabled:opacity-100",
                "data-[edited=true]:border-transparent"
              )}
              defaultValue={replicas}
            />
            {replicasChange !== undefined ? (
              <SubmitButton
                isPending={isPending}
                variant="outline"
                name="intent"
                value="cancel-service-change"
                className={cn(
                  "absolute bottom-1/2 translate-y-1/2 right-0.5 text-sm py-0 border-0",
                  "bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                )}
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
            ) : (
              !isEditing &&
              isMember && (
                <Button
                  variant="outline"
                  onClick={() => {
                    flushSync(() => {
                      setIsEditing(true);
                    });
                    inputRef.current?.focus();
                  }}
                  className={cn(
                    "absolute inset-y-0 right-0 text-sm border-0",
                    "bg-inherit inline-flex items-center gap-2 border-muted-foreground py-0.5"
                  )}
                >
                  <span>Edit</span>
                  <PencilLineIcon size={15} />
                </Button>
              )
            )}
          </div>
        </div>

        {isEditing && (
          <div className="flex gap-2 md:relative">
            <SubmitButton
              isPending={isPending}
              variant="outline"
              className="bg-inherit"
              name="intent"
              value="request-service-change"
            >
              {isPending ? (
                <>
                  <LoaderIcon className="animate-spin" size={15} />
                  <span className="sr-only">Updating service slug...</span>
                </>
              ) : (
                <>
                  <CheckIcon size={15} className="flex-none" />
                  <span className="sr-only">Update service slug</span>
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
      </FieldSet>
    </fetcher.Form>
  );
}
