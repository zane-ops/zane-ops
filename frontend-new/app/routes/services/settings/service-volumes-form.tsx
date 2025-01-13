import {
  AlertCircleIcon,
  ArrowRightIcon,
  CheckIcon,
  CopyIcon,
  ExternalLinkIcon,
  HardDrive,
  InfoIcon,
  LoaderIcon,
  Plus,
  PlusIcon,
  Route,
  Trash2Icon,
  TriangleAlertIcon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import { Form } from "react-router";
import { toast } from "sonner";
import { Code } from "~/components/code";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from "~/components/ui/accordion";
import { Alert, AlertDescription, AlertTitle } from "~/components/ui/alert";
import { Button, SubmitButton } from "~/components/ui/button";
import { Checkbox } from "~/components/ui/checkbox";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetErrors,
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { type DockerService } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceVolumesFormProps = {
  project_slug: string;
  service_slug: string;
};

export function ServiceVolumesForm({
  project_slug,
  service_slug
}: ServiceVolumesFormProps) {
  const { data: service } = useServiceQuery({ project_slug, service_slug });
  const volumes: Map<string, VolumeItem> = new Map();
  for (const url of service?.volumes ?? []) {
    volumes.set(url.id, {
      ...url,
      id: url.id
    });
  }
  for (const ch of (service?.unapplied_changes ?? []).filter(
    (ch) => ch.field === "volumes"
  )) {
    const newUrl = (ch.new_value ?? ch.old_value) as Omit<
      DockerService["volumes"][number],
      "id"
    >;
    volumes.set(ch.item_id ?? ch.id, {
      ...newUrl,
      change_id: ch.id,
      id: ch.item_id,
      change_type: ch.type
    });
  }

  return (
    <div className="flex flex-col gap-5 max-w-4xl w-full">
      <div className="flex flex-col gap-3">
        <p className="text-gray-400">
          Used for persisting the data from your services.
        </p>

        <Alert variant="warning">
          <TriangleAlertIcon size={15} />
          <AlertTitle>Warning</AlertTitle>
          <AlertDescription>
            Adding volumes will disable&nbsp;
            <a href="#" className="underline inline-flex gap-1 items-center">
              zero-downtime deployments <ExternalLinkIcon size={12} />
            </a>
            .
          </AlertDescription>
        </Alert>
      </div>
      {volumes.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-2">
            {[...volumes.entries()].map(([key, volume]) => (
              <li key={key}>
                <ServiceVolumeItem {...volume} />
              </li>
            ))}
          </ul>
        </>
      )}
      <hr className="border-border" />
      <h3 className="text-lg">Add new volume</h3>
      <NewServiceVolumeForm />
    </div>
  );
}

type VolumeItem = {
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
  id?: string | null;
} & Omit<DockerService["volumes"][number], "id">;

function ServiceVolumeItem({
  id,
  name,
  container_path,
  host_path,
  change_type,
  mode,
  change_id
}: VolumeItem) {
  const [accordionValue, setAccordionValue] = React.useState("");
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [changedVolumeMode, setChangedVolumeMode] = React.useState(mode);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const modeSuffix = mode === "READ_ONLY" ? "read only" : "read & write";

  const {
    fetcher: updateFetcher,
    data,
    reset
  } = useFetcherWithCallbacks({
    onSuccess() {
      formRef.current?.reset();
      setAccordionValue("");
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;

        if (key === "mode") {
          SelectTriggerRef.current?.focus();
          return;
        }
        field?.focus();
      }
    }
  });

  const { fetcher: cancelFetcher } = useFetcherWithCallbacks({
    onSuccess() {
      setAccordionValue("");
    }
  });
  const { fetcher: deleteFetcher } = useFetcherWithCallbacks({
    onSuccess() {
      setAccordionValue("");
    }
  });

  const errors = getFormErrorsFromResponseData(data?.errors);
  const isPending = updateFetcher.state !== "idle";
  return (
    <div className="relative group">
      <div
        className="absolute top-2 right-2 inline-flex gap-1 items-center"
        role="none"
      >
        {change_id !== undefined && (
          <cancelFetcher.Form
            method="post"
            id={`cancel-${change_id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="volumes" />
            <input type="hidden" name="change_id" value={change_id} />
          </cancelFetcher.Form>
        )}
        {id && (
          <deleteFetcher.Form
            method="post"
            id={`delete-${id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="volumes" />
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
                  className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                  type="submit"
                  name="intent"
                  value="cancel-service-change"
                  form={`cancel-${change_id}-form`}
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
                    className="px-2.5 py-0.5 md:opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
                    type="submit"
                    form={`delete-${id}-form`}
                    name="intent"
                    value="request-service-change"
                  >
                    <Trash2Icon size={15} className="flex-none text-red-400" />
                    <span className="sr-only">Delete url</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete url</TooltipContent>
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
          value={`${name}`}
          className="border-none"
          disabled={!!change_id}
        >
          <AccordionTrigger
            className={cn("rounded-md p-4 flex items-start gap-2 bg-muted", {
              "dark:bg-secondary-foreground bg-secondary/60 ":
                change_type === "UPDATE",
              "dark:bg-primary-foreground bg-primary/60": change_type === "ADD",
              "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
            })}
          >
            <HardDrive size={20} className="text-grey relative top-1.5" />
            <div className="flex flex-col gap-2">
              <h3 className="text-lg inline-flex gap-1 items-center">
                <span>{name}</span>
              </h3>
              <small className="text-card-foreground inline-flex gap-1 items-center">
                {host_path && (
                  <>
                    <span>{host_path}</span>
                    <ArrowRightIcon size={15} className="text-grey" />
                  </>
                )}
                <span className="text-grey">{container_path}</span>
                <Code>{modeSuffix}</Code>
              </small>
            </div>
          </AccordionTrigger>
          {id && (
            <AccordionContent className="border-border border-x border-b rounded-b-md p-4 mb-4">
              <updateFetcher.Form
                method="post"
                ref={formRef}
                className={cn("flex flex-col gap-4 w-full")}
              >
                <input type="hidden" name="change_field" value="volumes" />
                <input type="hidden" name="change_type" value="UPDATE" />
                <input type="hidden" name="item_id" value={id} />
                <FieldSet
                  errors={errors.new_value?.mode}
                  name="mode"
                  className="flex flex-col gap-1.5 flex-1"
                >
                  <label
                    htmlFor={`volume_mode-${id}`}
                    className="text-muted-foreground"
                  >
                    Mode
                  </label>
                  <FieldSetSelect
                    value={changedVolumeMode}
                    onValueChange={(mode) =>
                      setChangedVolumeMode(mode as VolumeMode)
                    }
                  >
                    <SelectTrigger
                      id={`volume_mode-${id}`}
                      ref={SelectTriggerRef}
                    >
                      <SelectValue placeholder="Select a volume mode" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="READ_WRITE">Read & Write</SelectItem>
                      <SelectItem value="READ_ONLY">Read only</SelectItem>
                    </SelectContent>
                  </FieldSetSelect>
                </FieldSet>
                <FieldSet
                  errors={errors.new_value?.name}
                  name="name"
                  className="flex flex-col gap-1.5 flex-1"
                >
                  <FieldSetLabel className="text-muted-foreground">
                    Name
                  </FieldSetLabel>
                  <FieldSetInput
                    placeholder="ex: postgresl-data"
                    defaultValue={name}
                  />
                </FieldSet>

                <FieldSet
                  name="container_path"
                  className="flex flex-col gap-1.5 flex-1"
                  errors={errors.new_value?.container_path}
                >
                  <FieldSetLabel className="text-muted-foreground">
                    Container path
                  </FieldSetLabel>
                  <FieldSetInput
                    placeholder="ex: /data"
                    defaultValue={container_path}
                  />
                </FieldSet>
                <FieldSet
                  name="host_path"
                  errors={errors.new_value?.host_path}
                  className="flex flex-col gap-1.5 flex-1"
                >
                  <FieldSetLabel className="text-muted-foreground">
                    Host path
                  </FieldSetLabel>
                  <FieldSetInput
                    placeholder="ex: /etc/localtime"
                    defaultValue={host_path ?? ""}
                  />
                </FieldSet>

                <hr className="-mx-4 border-border" />
                <div className="flex justify-end items-center gap-2">
                  <SubmitButton
                    isPending={isPending}
                    variant="secondary"
                    className="flex-1 md:flex-none"
                    name="intent"
                    value="request-service-change"
                  >
                    {isPending ? (
                      <>
                        <span>Updating...</span>
                        <LoaderIcon className="animate-spin" size={15} />
                      </>
                    ) : (
                      <>
                        <span>Update</span>
                        <PlusIcon size={15} />
                      </>
                    )}
                  </SubmitButton>
                  <Button
                    variant="outline"
                    type="reset"
                    className="flex-1 md:flex-none"
                    onClick={() => {
                      reset();
                      setChangedVolumeMode(mode);
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

type VolumeMode = DockerService["volumes"][number]["mode"];

function NewServiceVolumeForm() {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSuccess() {
      formRef.current?.reset();
      (
        formRef.current?.elements.namedItem(
          "container_path"
        ) as HTMLInputElement
      )?.focus();
      setVolumeMode("READ_WRITE");
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;

        if (key === "mode") {
          SelectTriggerRef.current?.focus();
          return;
        }

        field?.focus();
      }
    }
  });
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  const [volumeMode, setVolumeMode] = React.useState<VolumeMode>("READ_WRITE");

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 w-full border border-border rounded-md p-4"
    >
      <input type="hidden" name="change_field" value="volumes" />
      <input type="hidden" name="change_type" value="ADD" />

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
        errors={errors.new_value?.mode}
        name="mode"
        className="flex flex-col gap-1.5 flex-1"
      >
        <label htmlFor="volume_mode" className="text-muted-foreground">
          Mode
        </label>
        <FieldSetSelect
          value={volumeMode}
          onValueChange={(mode) => setVolumeMode(mode as VolumeMode)}
        >
          <SelectTrigger id="volume_mode" ref={SelectTriggerRef}>
            <SelectValue placeholder="Select a volume mode" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="READ_WRITE">Read & Write</SelectItem>
            <SelectItem value="READ_ONLY">Read only</SelectItem>
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <FieldSet
        errors={errors.new_value?.container_path}
        name="container_path"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel className="text-muted-foreground">
          Container path
        </FieldSetLabel>
        <FieldSetInput placeholder="ex: /data" />
      </FieldSet>
      <FieldSet
        name="host_path"
        errors={errors.new_value?.host_path}
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel className="text-muted-foreground">
          Host path
        </FieldSetLabel>
        <FieldSetInput placeholder="ex: /etc/localtime" />
      </FieldSet>
      <FieldSet
        errors={errors.new_value?.name}
        name="name"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel className="text-muted-foreground">Name</FieldSetLabel>
        <FieldSetInput placeholder="ex: postgresl-data" />
      </FieldSet>

      <hr className="-mx-4 border-border" />
      <div className="flex justify-end items-center gap-2">
        <SubmitButton
          isPending={isPending}
          variant="secondary"
          className="flex-1 md:flex-none"
          value="request-service-change"
          name="intent"
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
          variant="outline"
          type="reset"
          className="flex-1 md:flex-none"
          onClick={() => {
            reset();
            setVolumeMode("READ_WRITE");
          }}
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
