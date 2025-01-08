import { useQuery } from "@tanstack/react-query";
import { CheckIcon, LoaderIcon } from "lucide-react";
import * as React from "react";
import { apiClient } from "~/api/client";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSlider
} from "~/components/ui/fieldset";
import { Slider } from "~/components/ui/slider";
import type { DockerService } from "~/lib/queries";
import { getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceResourceLimitsProps = {
  project_slug: string;
  service_slug: string;
};

export function ServiceResourceLimits({
  project_slug,
  service_slug
}: ServiceResourceLimitsProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug
  });
  const { fetcher, data, reset } = useFetcherWithCallbacks({});
  const resourceLimitsQuery = useQuery({
    queryKey: ["SERVICE_RESOURCE_LIMITS"],
    queryFn: async () => {
      const { data } = await apiClient.GET("/api/server/resource-limits/");
      return data;
    },
    staleTime: Number.MAX_SAFE_INTEGER
  });

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const cpuInputRef = React.useRef<React.ComponentRef<"input">>(null);
  const memoryInputRef = React.useRef<React.ComponentRef<"input">>(null);

  const resouceLimitsChange = service.unapplied_changes.find(
    (change) => change.field === "resource_limits"
  );
  const isPending = fetcher.state !== "idle";

  const newResourceLimits =
    resouceLimitsChange?.new_value as DockerService["resource_limits"];
  const resource_limits =
    newResourceLimits === null
      ? null
      : newResourceLimits ?? service?.resource_limits;

  const [cpuLimit, setCPULimit] = React.useState<number | null>(
    resource_limits?.cpus ?? null
  );
  const [memoryLimit, setMemoryLimit] = React.useState<number | null>(
    resource_limits?.memory?.value ?? null
  );
  const max_memory_in_mb = Math.floor(
    (resourceLimitsQuery.data?.max_memory_in_bytes ?? 0) / (1024 * 1024)
  );

  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 w-full items-start max-w-4xl"
    >
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
          >
            <div className="flex justify-between gap-4 items-center">
              <FieldSetLabel>CPU</FieldSetLabel>
              <FieldSetInput
                className="inline-flex placeholder-shown:font-mono shrink w-28"
                placeholder="<no-limit>"
                defaultValue={resource_limits?.cpus ?? ""}
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
              min={0}
              value={[cpuLimit ?? 0]}
              onValueChange={(value) => {
                setCPULimit(value[0]);
                if (cpuInputRef.current) {
                  cpuInputRef.current.value = value[0].toString();
                }
              }}
              max={resourceLimitsQuery.data?.no_of_cpus}
            />
          </FieldSet>
          <FieldSet
            name="memory"
            className="flex flex-col gap-2"
            errors={errors.new_value?.memory?.value}
          >
            <div className="flex justify-between gap-4 items-center">
              <FieldSetLabel>Memory (in MiB)</FieldSetLabel>
              <FieldSetInput
                ref={memoryInputRef}
                className="inline-flex placeholder-shown:font-mono shrink w-28"
                placeholder="<no-limit>"
                defaultValue={resource_limits?.memory?.value ?? ""}
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
              value={[memoryLimit ?? 0]}
              onValueChange={(value) => {
                setMemoryLimit(value[0]);
                if (memoryInputRef.current) {
                  memoryInputRef.current.value = value[0].toString();
                }
              }}
              max={max_memory_in_mb}
            />
          </FieldSet>
        </div>
        <div className="flex items-center gap-2">
          <SubmitButton
            isPending={isPending}
            variant="secondary"
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
          <Button
            variant="outline"
            onClick={() => {
              reset();
              setCPULimit(null);
              setMemoryLimit(null);
            }}
            type="reset"
            className="flex-1 md:flex-none"
          >
            Reset
          </Button>
        </div>
      </fieldset>
    </fetcher.Form>
  );
}
