import {
  ArrowRightIcon,
  CheckIcon,
  ExternalLinkIcon,
  LoaderIcon,
  PlusIcon,
  Trash2Icon,
  TriangleAlertIcon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { useFetcher } from "react-router";
import { Code } from "~/components/code";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { DockerService } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  type clientAction,
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServicePortsFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServicePortsForm({
  service_slug,
  project_slug
}: ServicePortsFormProps) {
  const { data: service } = useServiceQuery({ project_slug, service_slug });
  const ports: Map<string, ServicePortItemProps> = new Map();
  for (const port of service.ports ?? []) {
    ports.set(port.id, {
      id: port.id,
      host: port.host,
      forwarded: port.forwarded
    });
  }
  for (const ch of (service.unapplied_changes ?? []).filter(
    (ch) => ch.field === "ports"
  )) {
    const hostForwarded = (ch.new_value ?? ch.old_value) as {
      host: number;
      forwarded: number;
    };
    ports.set(ch.item_id ?? ch.id, {
      change_id: ch.id,
      id: ch.item_id,
      host: hostForwarded.host,
      forwarded: hostForwarded.forwarded,
      change_type: ch.type
    });
  }

  return (
    <div className="w-full max-w-4xl flex flex-col gap-5">
      <div className="flex flex-col gap-3">
        <h3 className="text-lg">Exposed ports</h3>
        <p className="text-gray-400">
          This makes the service reachable externally via the ports defined
          in&nbsp;
          <Code>host port</Code>. Using&nbsp;
          <Code>80</Code>
          &nbsp;or&nbsp;
          <Code>443</Code>
          &nbsp;will create a default URL for the service.
        </p>

        <Alert variant="warning">
          <TriangleAlertIcon size={15} />
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            Using a host value other than 80 or 443 will disable&nbsp;
            <a
              href="#"
              className="text-link underline inline-flex gap-1 items-center"
            >
              zero-downtime deployments <ExternalLinkIcon size={12} />
            </a>
            .
          </AlertDescription>
        </Alert>
      </div>

      {ports.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-1">
            {[...ports.entries()].map(([key, value]) => (
              <li key={key}>
                <ServicePortItem
                  host={value.host}
                  forwarded={value.forwarded}
                  change_type={value.change_type}
                  change_id={value.change_id}
                  id={value.id}
                />
              </li>
            ))}
          </ul>
        </>
      )}

      <hr className="border-border" />
      <h3 className="text-lg">Add new port</h3>
      <NewServicePortForm />
    </div>
  );
}

type ServicePortItemProps = {
  change_id?: string;
  id?: string | null;
  change_type?: "UPDATE" | "DELETE" | "ADD";
} & Omit<DockerService["ports"][number], "id">;

function ServicePortItem({
  host,
  forwarded,
  change_id,
  id,
  change_type
}: ServicePortItemProps) {
  const [accordionValue, setAccordionValue] = React.useState("");
  const updateFetcher = useFetcher<typeof clientAction>();
  const isUpdatingExposedPort = updateFetcher.state !== "idle";
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const [data, setData] = React.useState(updateFetcher.data);
  const cancelFetcher = useFetcher<typeof clientAction>();
  const deleteFetcher = useFetcher<typeof clientAction>();

  React.useEffect(() => {
    setData(updateFetcher.data);

    if (updateFetcher.state === "idle" && !updateFetcher.data?.errors) {
      formRef.current?.reset();
      setAccordionValue("");
    }
  }, [updateFetcher.data, updateFetcher.state]);

  React.useEffect(() => {
    const cancelSuccessful =
      cancelFetcher.state === "idle" &&
      cancelFetcher.data &&
      !cancelFetcher.data.errors;
    const deleteSuccessful =
      deleteFetcher.state === "idle" &&
      deleteFetcher.data &&
      !deleteFetcher.data.errors;
    if (cancelSuccessful || deleteSuccessful) {
      setAccordionValue("");
    }
  }, [cancelFetcher.state, deleteFetcher.state]);

  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <div className="relative group">
      <div className="absolute top-1 right-2">
        {change_id !== undefined && (
          <cancelFetcher.Form
            method="post"
            id={`cancel-${change_id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="ports" />
            <input type="hidden" name="change_id" value={change_id} />
          </cancelFetcher.Form>
        )}
        {id && (
          <deleteFetcher.Form
            method="post"
            id={`delete-${id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="ports" />
            <input type="hidden" name="change_type" value="DELETE" />
            <input type="hidden" name="item_id" value={id} />
          </deleteFetcher.Form>
        )}
        <TooltipProvider>
          {change_id !== undefined ? (
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  type="submit"
                  name="intent"
                  value="cancel-service-change"
                  form={`cancel-${change_id}-form`}
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100 group-focus:opacity-100"
                >
                  <Undo2Icon size={15} className="flex-none" />
                  <span className="sr-only">Discard change</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Discard change</TooltipContent>
            </Tooltip>
          ) : (
            id && (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    type="submit"
                    form={`delete-${id}-form`}
                    name="intent"
                    value="request-service-change"
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete exposed port</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete exposed port</TooltipContent>
              </Tooltip>
            )
          )}
        </TooltipProvider>
      </div>

      <Accordion
        type="single"
        collapsible
        value={accordionValue}
        onValueChange={(state) => {
          setAccordionValue(state);
        }}
      >
        <AccordionItem
          value={`${host}:${forwarded}`}
          className="border-none"
          disabled={!!change_id}
        >
          <AccordionTrigger
            className={cn(
              "w-full px-3 bg-muted rounded-md inline-flex gap-2 items-center text-start flex-wrap pr-24",
              "data-[state=open]:rounded-b-none",
              {
                "dark:bg-secondary-foreground bg-secondary/60 ":
                  change_type === "UPDATE",
                "dark:bg-primary-foreground bg-primary/60":
                  change_type === "ADD",
                "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
              }
            )}
          >
            <span>{host}</span>
            <ArrowRightIcon size={15} className="text-grey" />
            <span className="text-grey">{forwarded}</span>
          </AccordionTrigger>
          {id && (
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <updateFetcher.Form
                method="post"
                ref={formRef}
                className="flex flex-col gap-4"
              >
                <input type="hidden" name="change_field" value="ports" />
                <input type="hidden" name="change_type" value="UPDATE" />
                <input type="hidden" name="item_id" value={id} />
                <div className="flex flex-col md:flex-row md:items-start gap-4">
                  <fieldset className="flex-1 inline-flex flex-col gap-1">
                    <label
                      className="text-gray-400"
                      htmlFor={`forwarded-${id}`}
                    >
                      Forwarded port
                    </label>
                    <Input
                      placeholder="ex: 8080"
                      id={`forwarded-${id}`}
                      defaultValue={forwarded}
                      name="forwarded"
                      aria-invalid={Boolean(errors.new_value?.forwarded)}
                      aria-labelledby={`forwarded-error-${id}`}
                    />

                    {errors.new_value?.forwarded && (
                      <span
                        className="text-red-500 text-sm"
                        id={`forwarded-error-${id}`}
                      >
                        {errors.new_value?.forwarded}
                      </span>
                    )}
                  </fieldset>
                  <fieldset className="flex-1 inline-flex flex-col gap-1">
                    <label htmlFor={`host-${id}`} className="text-gray-400">
                      Host port
                    </label>
                    <Input
                      placeholder="ex: 80"
                      defaultValue={host ?? 80}
                      id={`host-${id}`}
                      name="host"
                      aria-invalid={Boolean(errors.new_value?.host)}
                      aria-labelledby={`host-error-${id}`}
                    />

                    {errors.new_value?.host && (
                      <span
                        className="text-red-500 text-sm"
                        id={`host-error-${id}`}
                      >
                        {errors.new_value?.host}
                      </span>
                    )}
                  </fieldset>
                </div>

                <div className="flex justify-end items-center gap-2 border-t pt-4 px-4 -mx-4 border-border">
                  <SubmitButton
                    variant="secondary"
                    isPending={isUpdatingExposedPort}
                    className="inline-flex gap-1"
                    name="intent"
                    value="request-service-change"
                  >
                    {isUpdatingExposedPort ? (
                      <>
                        <span>Updating...</span>
                        <LoaderIcon className="animate-spin" size={15} />
                      </>
                    ) : (
                      <>
                        Update
                        <CheckIcon size={15} />
                      </>
                    )}
                  </SubmitButton>
                  <Button
                    variant="outline"
                    type="reset"
                    onClick={() => {
                      setData(undefined);
                    }}
                  >
                    Reset
                  </Button>
                </div>
              </updateFetcher.Form>
            </AccordionContent>
          )}
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function NewServicePortForm() {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;
        field?.focus();
      }
    },
    onSuccess() {
      formRef.current?.reset();
      (
        formRef.current?.elements.namedItem("forwarded") as HTMLInputElement
      )?.focus();
    }
  });
  const isPending = fetcher.state !== "idle";

  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex md:items-start gap-3 md:flex-row flex-col items-stretch"
    >
      <input type="hidden" name="change_field" value="ports" />
      <input type="hidden" name="change_type" value="ADD" />
      <FieldSet
        errors={errors.new_value?.forwarded}
        className="flex-1 inline-flex flex-col gap-1"
      >
        <FieldSetLabel className="text-gray-400">Forwarded port</FieldSetLabel>
        <FieldSetInput placeholder="ex: 8080" name="forwarded" />
      </FieldSet>
      <FieldSet
        errors={errors.new_value?.host}
        className="flex-1 inline-flex flex-col gap-1"
      >
        <FieldSetLabel className="text-gray-400">Host port</FieldSetLabel>
        <FieldSetInput placeholder="ex: 80" defaultValue={80} name="host" />
      </FieldSet>

      <div className="flex gap-3 items-center pt-7 w-full md:w-auto">
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          className="inline-flex gap-1 flex-1"
          name="intent"
          value="request-service-change"
        >
          {isPending ? (
            <>
              <span>Adding...</span>
              <LoaderIcon className="animate-spin" size={15} />
            </>
          ) : (
            <>
              <span>Add</span>
              <PlusIcon size={15} />
            </>
          )}
        </SubmitButton>
        <Button
          onClick={reset}
          variant="outline"
          type="reset"
          className="flex-1"
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
