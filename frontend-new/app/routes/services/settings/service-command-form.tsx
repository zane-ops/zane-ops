import { CheckIcon, LoaderIcon, Undo2Icon } from "lucide-react";
import * as React from "react";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceCommandFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServiceCommandForm({
  project_slug,
  service_slug
}: ServiceCommandFormProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug
  });
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSettled(data) {
      if (!data.errors) {
        formRef.current?.reset();
      } else {
        (
          formRef.current?.elements.namedItem("command") as HTMLInputElement
        )?.focus();
      }
    }
  });

  const startingCommandChange = service?.unapplied_changes.find(
    (change) => change.field === "command"
  );
  const isEmptyChange =
    startingCommandChange !== undefined &&
    startingCommandChange.new_value === null;

  const command = isEmptyChange
    ? ""
    : (startingCommandChange?.new_value as string) ?? service?.command;

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = fetcher.state !== "idle";

  return (
    <fetcher.Form
      ref={formRef}
      method="post"
      className="flex flex-col gap-4 w-full items-start max-w-4xl"
    >
      <input type="hidden" name="change_field" value="command" />
      <input type="hidden" name="change_type" value="UPDATE" />

      {startingCommandChange !== undefined && (
        <>
          <input
            type="hidden"
            name="change_id"
            value={startingCommandChange.id}
          />
        </>
      )}

      <FieldSet
        name="command"
        errors={errors.new_value}
        className="w-full flex flex-col gap-4"
      >
        <legend className="text-lg">Custom start command</legend>
        <p className="text-gray-400">
          Command executed at the start of each new deployment.
        </p>
        <div className="flex flex-col gap-1.5 flex-1">
          <FieldSetLabel className="text-muted-foreground sr-only">
            Value
          </FieldSetLabel>
          <FieldSetInput
            placeholder={isEmptyChange ? "<empty>" : "ex: npm run start"}
            disabled={startingCommandChange !== undefined}
            className={cn(
              "disabled:placeholder-shown:font-mono disabled:bg-secondary/60",
              "dark:disabled:bg-secondary-foreground disabled:opacity-100",
              "disabled:border-transparent"
            )}
            defaultValue={command}
          />
        </div>
      </FieldSet>

      <div className="inline-flex items-center gap-2">
        {startingCommandChange !== undefined ? (
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
                  <span>Updating ...</span>
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
              onClick={reset}
              type="reset"
              className="flex-1 md:flex-none"
            >
              Reset
            </Button>
          </>
        )}
      </div>
    </fetcher.Form>
  );
}
