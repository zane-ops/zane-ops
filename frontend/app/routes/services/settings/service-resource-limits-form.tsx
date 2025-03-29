import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckIcon,
  LoaderIcon,
  Trash2Icon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Slider } from "~/components/ui/slider";
import { type Service, serverQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceResourceLimitsProps = {
  project_slug: string;
  service_slug: string;
  env_slug: string;
};

export function ServiceResourceLimits({
  project_slug,
  service_slug,
  env_slug
}: ServiceResourceLimitsProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });
  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSuccess(data) {
      formRef.current?.reset();
      const service = data.data!;
      let updatedResourceLimits = resourceLimits;
      if ("resource_limits" in service) {
        const resouceLimitsChange = service.unapplied_changes.find(
          (change) => change.field === "resource_limits"
        );
        const newResourceLimits =
          resouceLimitsChange?.new_value as Service["resource_limits"];
        updatedResourceLimits =
          newResourceLimits === null
            ? null
            : newResourceLimits ?? service?.resource_limits;
      }

      setCPULimit(updatedResourceLimits?.cpus ?? null);
      setMemoryLimit(updatedResourceLimits?.memory?.value ?? null);
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];

        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
      }
    }
  });
  const resourceLimitsQuery = useQuery(serverQueries.resourceLimits);

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const cpuInputRef = React.useRef<React.ComponentRef<"input">>(null);
  const memoryInputRef = React.useRef<React.ComponentRef<"input">>(null);

  const resouceLimitsChange = service.unapplied_changes.find(
    (change) => change.field === "resource_limits"
  );
  const isPending = fetcher.state !== "idle";

  const newResourceLimits =
    resouceLimitsChange?.new_value as Service["resource_limits"];
  const resourceLimits =
    newResourceLimits === null
      ? null
      : newResourceLimits ?? service?.resource_limits;

  const [cpuLimit, setCPULimit] = React.useState<number | null>(
    resourceLimits?.cpus ?? null
  );
  const [memoryLimit, setMemoryLimit] = React.useState<number | null>(
    resourceLimits?.memory?.value ?? null
  );
  const max_memory_in_mb = Math.floor(
    (resourceLimitsQuery.data?.max_memory_in_bytes ?? 0) / (1024 * 1024)
  );

  const errors = getFormErrorsFromResponseData(data?.errors);
  const non_field_errors = Array.isArray(errors.new_value)
    ? [...errors.new_value, ...(errors.non_field_errors ?? [])]
    : errors.non_field_errors;

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 w-full items-start max-w-4xl"
    >
      {non_field_errors && (
        <Alert variant="destructive">
          <AlertCircleIcon className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{non_field_errors}</AlertDescription>
        </Alert>
      )}

      <input type="hidden" name="change_field" value="resource_limits" />
      <input type="hidden" name="change_type" value="UPDATE" />
      {resouceLimitsChange !== undefined && (
        <input type="hidden" name="change_id" value={resouceLimitsChange.id} />
      )}

      <fieldset
        className="w-full flex flex-col gap-5"
        disabled={resourceLimitsQuery.isLoading}
      >
        <legend className="text-lg">Resource Limits</legend>
        <p className="text-gray-400">
          Max amount of CPUs and Memory to allocate for this service.
        </p>

        <div className="flex flex-col gap-4">
          <FieldSet
            name="cpus"
            className="flex flex-col gap-2"
            errors={errors.new_value?.cpus}
            disabled={resouceLimitsChange !== undefined}
          >
            <div className="flex justify-between gap-4 items-center">
              <FieldSetLabel>CPU</FieldSetLabel>
              <FieldSetInput
                className={cn(
                  "inline-flex placeholder-shown:font-mono shrink w-28",
                  "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                  "dark:disabled:bg-secondary-foreground disabled:opacity-100",
                  "disabled:border-transparent"
                )}
                placeholder="<no-limit>"
                defaultValue={resourceLimits?.cpus ?? ""}
                ref={cpuInputRef}
                onChange={(ev) => {
                  if (!Number.isNaN(ev.currentTarget.value)) {
                    setCPULimit(Number(ev.currentTarget.value));
                  }
                }}
              />
            </div>
            <Slider
              step={0.5}
              min={0.1}
              aria-hidden="true"
              value={[cpuLimit ?? resourceLimitsQuery.data?.no_of_cpus ?? 0]}
              disabled={resouceLimitsChange !== undefined}
              onValueChange={(value) => {
                setCPULimit(value[0]);
                if (cpuInputRef.current) {
                  cpuInputRef.current.value = value[0].toString();
                }
              }}
              max={resourceLimitsQuery.data?.no_of_cpus}
            />
            <div className="flex items-center justify-between text-gray-400">
              <span>0.1</span>
              <span>{resourceLimitsQuery.data?.no_of_cpus}</span>
            </div>
          </FieldSet>
          <FieldSet
            name="memory"
            className="flex flex-col gap-2"
            errors={errors.new_value?.memory?.value}
            disabled={resouceLimitsChange !== undefined}
          >
            <div className="flex justify-between gap-4 items-center">
              <FieldSetLabel>Memory (in MiB)</FieldSetLabel>
              <FieldSetInput
                ref={memoryInputRef}
                placeholder="<no-limit>"
                className={cn(
                  "inline-flex placeholder-shown:font-mono shrink w-28",
                  "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                  "dark:disabled:bg-secondary-foreground disabled:opacity-100",
                  "disabled:border-transparent"
                )}
                defaultValue={resourceLimits?.memory?.value ?? ""}
                onChange={(ev) => {
                  if (!Number.isNaN(ev.currentTarget.value)) {
                    setMemoryLimit(Number(ev.currentTarget.value));
                  }
                }}
              />
            </div>

            <Slider
              step={100}
              min={0}
              aria-hidden="true"
              value={[memoryLimit ?? max_memory_in_mb]}
              disabled={resouceLimitsChange !== undefined}
              onValueChange={(value) => {
                setMemoryLimit(value[0]);
                if (memoryInputRef.current) {
                  memoryInputRef.current.value = value[0].toString();
                }
              }}
              max={max_memory_in_mb}
            />
            <div className="flex items-center justify-between text-gray-400">
              <span>0</span>
              <span>{max_memory_in_mb}</span>
            </div>
          </FieldSet>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {resouceLimitsChange ? (
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
          ) : (
            <>
              <SubmitButton
                isPending={isPending}
                variant="secondary"
                name="intent"
                value="request-service-change"
                disabled={!resourceLimitsQuery.data}
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
              <Button
                variant="outline"
                onClick={() => {
                  reset();
                  setCPULimit(resourceLimits?.cpus ?? null);
                  setMemoryLimit(resourceLimits?.memory?.value ?? null);
                }}
                type="reset"
              >
                Reset
              </Button>
              {service?.resource_limits !== null && resourceLimits !== null && (
                <SubmitButton
                  value="remove-service-resource-limits"
                  name="intent"
                  isPending={isPending}
                  variant="destructive"
                  className="inline-flex gap-1 items-center"
                >
                  {isPending ? (
                    <>
                      <LoaderIcon className="animate-spin" size={15} />
                      <span>Removing...</span>
                    </>
                  ) : (
                    <>
                      <Trash2Icon size={15} className="flex-none" />
                      <span>Remove limits</span>
                    </>
                  )}
                </SubmitButton>
              )}
            </>
          )}
        </div>
      </fieldset>
    </fetcher.Form>
  );
}
