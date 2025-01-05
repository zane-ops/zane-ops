import { CheckIcon, LoaderIcon, Trash2Icon, Undo2Icon } from "lucide-react";
import * as React from "react";
import { Form } from "react-router";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue
} from "~/components/ui/select";
import type { DockerService } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceHealthcheckFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServiceHealthcheckForm({
  project_slug,
  service_slug
}: ServiceHealthcheckFormProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug
  });
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSettled(data) {
      if (!data.errors) {
        formRef.current?.reset();
        setHealthCheckType("none");
      } else {
        (
          formRef.current?.elements.namedItem("command") as HTMLInputElement
        )?.focus();
      }
    }
  });
  const healthcheckChange = service?.unapplied_changes.find(
    (change) => change.field === "healthcheck"
  );

  const newHealthCheck =
    healthcheckChange?.new_value as DockerService["healthcheck"];
  const healthcheck =
    newHealthCheck === null ? null : newHealthCheck ?? service?.healthcheck;

  const errors = getFormErrorsFromResponseData(data?.errors);

  const [healthcheckType, setHealthCheckType] = React.useState<
    NonNullable<DockerService["healthcheck"]>["type"] | "none"
  >(healthcheck?.type ?? "none");

  const isPending = fetcher.state !== "idle";

  return (
    <fetcher.Form
      ref={formRef}
      method="post"
      //   action={(formData) => {
      //     const remove = formData.get("remove")?.toString() === "true";
      //     if (remove) {
      //       removeHealthcheckCommandMutation.mutate(
      //         {
      //           type: "UPDATE",
      //           new_value: null
      //         },
      //         {
      //           onSuccess(errors) {
      //             if (!errors) {
      //               formRef.current?.reset();
      //               setHealthCheckType("none");
      //             }
      //           }
      //         }
      //       );
      //       return;
      //     }
      //     const revertChange =
      //       formData.get("revert_change")?.toString() === "true";
      //     if (revertChange && healthcheckChange?.id) {
      //       cancelHealthcheckChangeMutation.mutate(healthcheckChange.id, {
      //         onSuccess() {
      //           setHealthCheckType(service?.healthcheck?.type ?? "none");
      //           formRef.current?.reset();
      //         }
      //       });
      //       return;
      //     }

      //     updateHealthcheckCommandMutation.mutate(
      //       {
      //         type: "UPDATE",
      //         new_value: {
      //           type: formData.get("type")?.toString() as NonNullable<
      //             DockerService["healthcheck"]
      //           >["type"],
      //           value: formData.get("value")?.toString() ?? "",
      //           timeout_seconds: Number(
      //             formData.get("timeout_seconds")?.toString() || 30
      //           ),
      //           interval_seconds: Number(
      //             formData.get("interval_seconds")?.toString() || 30
      //           )
      //         }
      //       },
      //       {
      //         onSuccess(errors) {
      //           if (!errors) {
      //             formRef.current?.reset();
      //           }
      //         }
      //       }
      //     );
      //   }}
      className="flex flex-col gap-4 w-full items-start max-w-4xl"
    >
      <input type="hidden" name="change_field" value="healthcheck" />
      <input type="hidden" name="change_type" value="UPDATE" />

      {healthcheckChange !== undefined && (
        <input type="hidden" name="change_id" value={healthcheckChange.id} />
      )}

      <fieldset className="w-full flex flex-col gap-5">
        <legend className="text-lg">Healthcheck</legend>
        <p className="text-gray-400">
          ZaneOps uses this to verify if your app is running correctly for new
          deployments and ensures the deployment is successful before switching.
          This value will also be used to continously monitor your app.
        </p>

        <div className="flex flex-col md:flex-row md:items-start gap-2">
          <FieldSet
            errors={errors.new_value?.type}
            name="type"
            className="flex flex-col gap-1.5 flex-1"
          >
            <FieldSetLabel className="text-muted-foreground">
              Type
            </FieldSetLabel>
            <FieldSetSelect
              name="type"
              disabled={healthcheckChange !== undefined}
              value={healthcheckType}
              onValueChange={(value) =>
                setHealthCheckType(
                  value as NonNullable<DockerService["healthcheck"]>["type"]
                )
              }
            >
              <SelectTrigger
                className={cn(
                  "data-disabled:bg-secondary/60 dark:data-disabled:bg-secondary-foreground",
                  "data-disabled:opacity-100 data-disabled:border-transparent",
                  healthcheckType === "none" && "text-muted-foreground"
                )}
              >
                <SelectValue placeholder="Select a type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem disabled value="none">
                  Select a type
                </SelectItem>
                <SelectItem value="PATH">Path</SelectItem>
                <SelectItem value="COMMAND">Command</SelectItem>
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>
          <FieldSet
            name="value"
            errors={errors.new_value?.value}
            className="flex flex-col gap-1.5 flex-1"
          >
            <FieldSetLabel className="text-muted-foreground">
              Value
            </FieldSetLabel>
            <FieldSetInput
              disabled={healthcheckChange !== undefined}
              placeholder={
                healthcheckChange && healthcheck === null
                  ? "<empty>"
                  : healthcheckType === "COMMAND"
                    ? "ex: redis-cli ping"
                    : "ex: /healthcheck"
              }
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
                "dark:disabled:bg-secondary-foreground disabled:opacity-100",
                "disabled:border-transparent"
              )}
              defaultValue={healthcheck?.value}
            />
          </FieldSet>
        </div>
        <FieldSet
          errors={errors.new_value?.timeout_seconds}
          name="timeout_seconds"
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel className="text-muted-foreground">
            Timeout (in seconds)
          </FieldSetLabel>
          <FieldSetInput
            disabled={healthcheckChange !== undefined}
            placeholder={
              healthcheckChange && healthcheck === null ? "<empty>" : "ex: 30"
            }
            defaultValue={
              healthcheckChange && healthcheck === null
                ? ""
                : healthcheck?.timeout_seconds
            }
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
              "dark:disabled:bg-secondary-foreground disabled:opacity-100",
              "disabled:border-transparent"
            )}
          />
        </FieldSet>
        <FieldSet
          errors={errors.new_value?.interval_seconds}
          name="interval_seconds"
          className="flex flex-col gap-1.5 flex-1"
        >
          <FieldSetLabel className="text-muted-foreground">
            Interval (in seconds)
          </FieldSetLabel>
          <FieldSetInput
            placeholder={
              healthcheckChange && healthcheck === null ? "<empty>" : "ex: 30"
            }
            disabled={healthcheckChange !== undefined}
            defaultValue={
              healthcheckChange && healthcheck === null
                ? ""
                : healthcheck?.interval_seconds
            }
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
              "dark:disabled:bg-secondary-foreground disabled:opacity-100",
              "disabled:border-transparent"
            )}
          />
        </FieldSet>
      </fieldset>

      <div className="flex items-center gap-2">
        {healthcheckChange ? (
          <SubmitButton
            isPending={isPending}
            variant="outline"
            name="intent"
            value="cancel-service-change"
          >
            {isPending ? (
              <>
                <LoaderIcon className="animate-spin" size={15} />
                <span>Reverting...</span>
              </>
            ) : (
              <>
                <Undo2Icon size={15} className="flex-none" />
                <span>Revert change</span>
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
                setHealthCheckType(healthcheck?.type ?? "none");
              }}
              type="reset"
              className="flex-1 md:flex-none"
            >
              Reset
            </Button>

            {service?.healthcheck !== null && healthcheck !== null && (
              <SubmitButton
                value="true"
                name="remove"
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
                    <span>Remove healthcheck</span>
                  </>
                )}
              </SubmitButton>
            )}
          </>
        )}
      </div>
    </fetcher.Form>
  );
}
