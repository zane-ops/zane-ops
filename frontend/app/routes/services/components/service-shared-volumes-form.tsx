import { useQuery } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ExternalLinkIcon,
  HardDriveIcon,
  LoaderIcon,
  PlusIcon,
  Trash2Icon,
  Undo2Icon
} from "lucide-react";
import * as React from "react";
import type { Service } from "~/api/types";
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
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import {
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
import { serviceQueries } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/service-settings";

export type ServiceSharedVolumesFormProps = {
  project_slug: string;
  service_slug: string;
  env_slug: string;
};

export function ServiceSharedVolumesForm({
  project_slug,
  service_slug,
  env_slug
}: ServiceSharedVolumesFormProps) {
  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });
  const volumes: Map<string, SharedVolumeItem> = new Map();
  for (const volume of service?.shared_volumes ?? []) {
    volumes.set(volume.id, {
      ...volume,
      id: volume.id
    });
  }
  for (const ch of (service?.unapplied_changes ?? []).filter(
    (ch) => ch.field === "shared_volumes"
  )) {
    const newVolume = (ch.new_value ?? ch.old_value) as Omit<
      Service["shared_volumes"][number],
      "id"
    >;
    volumes.set(ch.item_id ?? ch.id, {
      ...newVolume,
      change_id: ch.id,
      id: ch.item_id,
      change_type: ch.type
    });
  }

  return (
    <div className="flex flex-col gap-5 max-w-4xl w-full">
      <div className="flex flex-col gap-3">
        <p className="text-gray-400">
          Share persistent data between services by mounting volumes from other
          services.&nbsp;
          <a
            href="https://zaneops.dev/knowledge-base/shared-volumes"
            target="_blank"
            className="text-link underline inline-flex gap-1 items-center"
          >
            documentation <ExternalLinkIcon size={12} />
          </a>
        </p>
      </div>
      {volumes.size > 0 && (
        <>
          <hr className="border-border" />
          <ul className="flex flex-col gap-2">
            {[...volumes.entries()].map(([key, volume]) => (
              <li key={key}>
                <ServiceSharedVolumeItem
                  {...volume}
                  service_slug={service_slug}
                  project_slug={project_slug}
                  env_slug={env_slug}
                />
              </li>
            ))}
          </ul>
        </>
      )}
      <hr className="border-border" />
      <h3 className="text-lg">Add new shared volume</h3>
      <NewServiceSharedVolumeForm
        service_slug={service_slug}
        project_slug={project_slug}
        env_slug={env_slug}
      />
    </div>
  );
}

type SharedVolumeItem = {
  change_id?: string;
  change_type?: "UPDATE" | "DELETE" | "ADD";
  id?: string | null;
} & Omit<Service["shared_volumes"][number], "id">;

function ServiceSharedVolumeItem({
  id,
  volume,
  volume_id,
  container_path,
  change_type,
  change_id,
  ...props
}: SharedVolumeItem & ServiceSharedVolumesFormProps) {
  const [accordionValue, setAccordionValue] = React.useState("");
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const [changedVolumeId, setChangedVolumeId] = React.useState(volume_id);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);
  const { data: volumes = [] } = useQuery(
    serviceQueries.availableVolumes(props)
  );

  const volumeMap = React.useMemo(() => {
    const map = new Map<string, typeof volume>([[volume.id, volume]]);

    for (const volume of volumes) {
      map.set(volume.id, volume);
    }

    return map;
  }, [volumes, volume]);

  console.log({
    volumeMap
  });

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

        if (key === "volume_id") {
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
            <input type="hidden" name="change_field" value="shared_volumes" />
            <input type="hidden" name="change_id" value={change_id} />
          </cancelFetcher.Form>
        )}
        {id && (
          <deleteFetcher.Form
            method="post"
            id={`delete-${id}-form`}
            className="hidden"
          >
            <input type="hidden" name="change_field" value="shared_volumes" />
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
                    <span className="sr-only">Delete volume</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Delete volume</TooltipContent>
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
          value={volume_id}
          className="border-none"
          disabled={!!change_id}
        >
          <AccordionTrigger
            className={cn(
              "rounded-md p-4 flex items-start gap-2 bg-muted",
              "aria-expanded:rounded-b-none",
              {
                "dark:bg-secondary-foreground bg-secondary/60 ":
                  change_type === "UPDATE",
                "dark:bg-primary-foreground bg-primary/60":
                  change_type === "ADD",
                "dark:bg-red-500/30 bg-red-400/60": change_type === "DELETE"
              }
            )}
          >
            <HardDriveIcon size={20} className="text-grey relative top-1.5" />
            <div className="flex flex-col gap-2">
              <h3 className="text-lg inline-flex gap-1 items-baseline">
                <span>{volume.name}</span>
                <small className="text-grey">
                  from <Code>{volume.service.slug}</Code>
                </small>
              </h3>
              <small className="text-card-foreground inline-flex gap-1 items-center">
                <span className="text-grey">{container_path}</span>
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
                <input
                  type="hidden"
                  name="change_field"
                  value="shared_volumes"
                />
                <input type="hidden" name="change_type" value="UPDATE" />
                <input type="hidden" name="item_id" value={id} />
                <FieldSet
                  errors={errors.new_value?.volume_id}
                  name="volume_id"
                  className="flex flex-col gap-1.5 flex-1"
                >
                  <label
                    htmlFor={`volume-${id}`}
                    className="text-muted-foreground"
                  >
                    Volume
                  </label>
                  <FieldSetSelect
                    value={changedVolumeId}
                    onValueChange={setChangedVolumeId}
                  >
                    <SelectTrigger id={`volume-${id}`} ref={SelectTriggerRef}>
                      <SelectValue placeholder="Select a volume" />
                    </SelectTrigger>
                    <SelectContent>
                      {volumeMap.size === 0 && (
                        <SelectItem disabled value="empty">
                          No volume available for sharing
                        </SelectItem>
                      )}

                      {[...volumeMap.entries()].map(([id, v]) => (
                        <SelectItem key={id} value={id}>
                          <div className="flex items-center gap-2">
                            <HardDriveIcon className="size-4" />
                            <span>{v.name}</span>
                            <span className="text-grey">{v.service.slug}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </FieldSetSelect>
                </FieldSet>

                <FieldSet
                  required
                  name="container_path"
                  className="flex flex-col gap-1.5 flex-1"
                  errors={errors.new_value?.container_path}
                >
                  <FieldSetLabel>Container path</FieldSetLabel>
                  <FieldSetInput
                    placeholder="ex: /data"
                    defaultValue={container_path}
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
                      setChangedVolumeId(volume_id);
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

function NewServiceSharedVolumeForm(props: ServiceSharedVolumesFormProps) {
  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);
  const { data: volumes = [], isLoading } = useQuery(
    serviceQueries.availableVolumes(props)
  );

  const [selectedVolumeId, setSelectedVolumeId] = React.useState<
    string | undefined
  >();

  const { fetcher, data, reset } = useFetcherWithCallbacks({
    onSuccess() {
      formRef.current?.reset();
      (
        formRef.current?.elements.namedItem(
          "container_path"
        ) as HTMLInputElement
      )?.focus();
    },
    onSettled(data) {
      if (data.errors) {
        const errors = getFormErrorsFromResponseData(data?.errors);
        const key = Object.keys(errors.new_value ?? {})[0];
        const field = formRef.current?.elements.namedItem(
          key
        ) as HTMLInputElement;

        if (key === "volume_id") {
          SelectTriggerRef.current?.focus();
          return;
        }

        field?.focus();
      }
    }
  });
  const isPending = fetcher.state !== "idle";
  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <fetcher.Form
      method="post"
      ref={formRef}
      className="flex flex-col gap-4 w-full border border-border rounded-md p-4"
    >
      <input type="hidden" name="change_field" value="shared_volumes" />
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
        errors={errors.new_value?.volume_id}
        name="volume_id"
        className="flex flex-col gap-1.5 flex-1"
      >
        <label htmlFor="volume_id" className="text-muted-foreground">
          Volume
        </label>
        <FieldSetSelect
          value={selectedVolumeId}
          onValueChange={setSelectedVolumeId}
        >
          <SelectTrigger id="volume_id" ref={SelectTriggerRef}>
            <SelectValue placeholder="Select a volume" />
          </SelectTrigger>
          <SelectContent>
            {isLoading ? (
              <SelectItem disabled value="loading">
                <div className="flex items-center gap-2 font-mono italic">
                  <LoaderIcon className="animate-spin size-4" />
                  Loading...
                </div>
              </SelectItem>
            ) : (
              volumes.length === 0 && (
                <SelectItem disabled value="empty">
                  No volume available for sharing
                </SelectItem>
              )
            )}

            {volumes.map((v) => (
              <SelectItem key={v.id} value={v.id}>
                <div className="flex items-center gap-2">
                  <HardDriveIcon className="size-4" />
                  <span>{v.name}</span>
                  <span className="text-grey">{v.service.slug}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </FieldSetSelect>
      </FieldSet>

      <FieldSet
        required
        errors={errors.new_value?.container_path}
        name="container_path"
        className="flex flex-col gap-1.5 flex-1"
      >
        <FieldSetLabel>Container path</FieldSetLabel>
        <FieldSetInput placeholder="ex: /data" />
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
            setSelectedVolumeId(undefined);
          }}
        >
          Reset
        </Button>
      </div>
    </fetcher.Form>
  );
}
