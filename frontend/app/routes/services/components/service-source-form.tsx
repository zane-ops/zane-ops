import { useQuery } from "@tanstack/react-query";
import {
  CheckIcon,
  ContainerIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { href, useFetcher } from "react-router";
import { toast } from "sonner";
import { useDebounce } from "use-debounce";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import {
  FieldSet,
  FieldSetLabel,
  FieldSetSelect
} from "~/components/ui/fieldset";
import { Input } from "~/components/ui/input";
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
import { DEFAULT_REGISTRIES } from "~/lib/constants";
import {
  type Service,
  dockerHubQueries,
  sharedRegistryCredentialsQueries
} from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  type clientAction,
  useServiceQuery
} from "~/routes/services/settings/service-settings";

export type ServiceFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

export function ServiceSourceForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const serviceSourcheChange = service.unapplied_changes.find(
    (change) => change.field === "source"
  ) as
    | {
        new_value: Pick<
          Service,
          "image" | "credentials" | "container_registry_credentials"
        >;
        id: string;
      }
    | undefined;

  const serviceImage = serviceSourcheChange?.new_value.image ?? service.image!;
  const imageParts = serviceImage.split(":");
  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  const container_registry_credentials_id =
    serviceSourcheChange?.new_value.container_registry_credentials?.id ??
    service.container_registry_credentials?.id;

  const errors = getFormErrorsFromResponseData(data?.errors);

  const [isComboxOpen, setComboxOpen] = React.useState(false);
  const [imageSearchQuery, setImageSearchQuery] = React.useState(serviceImage);
  const [containerRegistryCredentials, setContainerRegistryCredentials] =
    React.useState(container_registry_credentials_id);

  const formRef = React.useRef<React.ComponentRef<"form">>(null);
  const SelectTriggerRef =
    React.useRef<React.ComponentRef<typeof SelectTrigger>>(null);

  const [debouncedValue] = useDebounce(imageSearchQuery, 150);
  const { data: imageListData } = useQuery(
    dockerHubQueries.images(debouncedValue)
  );
  const { data: registries = [] } = useQuery(
    sharedRegistryCredentialsQueries.list
  );

  const imageList = imageListData?.data?.images ?? [];

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
        setImageSearchQuery(serviceImage);
        setContainerRegistryCredentials(container_registry_credentials_id);
      }
    }
  }, [
    fetcher.state,
    fetcher.data,
    serviceImage,
    container_registry_credentials_id
  ]);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col gap-4 w-full"
        ref={formRef}
      >
        <input type="hidden" name="change_field" value="source" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input
          type="hidden"
          name="change_id"
          value={serviceSourcheChange?.id}
        />
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="image">
            Source Image&nbsp;
            <span className="text-amber-600 dark:text-yellow-500">*</span>
          </label>
          <div className="relative">
            {!isEditing ? (
              <>
                <Input
                  id="image"
                  name="image"
                  ref={inputRef}
                  placeholder="image"
                  defaultValue={serviceImage}
                  aria-labelledby="image-error"
                  aria-invalid={Boolean(errors.new_value?.image)}
                  disabled={!isEditing || serviceSourcheChange !== undefined}
                  data-edited={
                    serviceSourcheChange !== undefined ? "true" : undefined
                  }
                  className={cn(
                    "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                    "data-[edited]:dark:disabled:bg-secondary-foreground",
                    "disabled:border-transparent disabled:opacity-100",
                    "disabled:text-transparent"
                  )}
                />
                <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
                  {image}
                  <span className="text-grey">:{tag}</span>
                </span>
              </>
            ) : (
              <Command shouldFilter={false} label="Image">
                <CommandInput
                  id="image"
                  onFocus={() => setComboxOpen(true)}
                  onValueChange={(query) => {
                    setImageSearchQuery(query);
                    setComboxOpen(true);
                  }}
                  onBlur={() => setComboxOpen(false)}
                  className="p-3"
                  value={imageSearchQuery}
                  placeholder="ex: bitnami/redis"
                  name="image"
                  aria-describedby="image-error"
                  aria-invalid={Boolean(errors.new_value?.image)}
                />
                <CommandList
                  className={cn({
                    "hidden!":
                      imageList.length === 0 ||
                      imageSearchQuery.trim().length === 0 ||
                      !isComboxOpen
                  })}
                >
                  {imageList.map((image) => (
                    <CommandItem
                      key={image.full_image}
                      value={image.full_image}
                      className="flex items-start gap-2"
                      onSelect={(value) => {
                        setImageSearchQuery(value);
                        setComboxOpen(false);
                      }}
                    >
                      <ContainerIcon
                        size={15}
                        className="flex-none relative top-1"
                      />
                      <div className="flex flex-row items-center gap-1">
                        <span>{image.full_image}</span>
                        <small className="text-xs text-gray-400/80">
                          {image.description}
                        </small>
                      </div>
                    </CommandItem>
                  ))}
                </CommandList>
              </Command>
            )}
          </div>
          {errors.new_value?.image && (
            <span id="image-error" className="text-red-500 text-sm">
              {errors.new_value?.image}
            </span>
          )}
        </fieldset>

        <fieldset className="w-full flex flex-col gap-2">
          <legend>Credentials</legend>
          <p className="text-gray-400">
            If your service pulls private Docker images from a registry
          </p>

          <FieldSet
            errors={errors.new_value?.container_registry_credentials_id}
            name="container_registry_credentials_id"
            className="flex flex-col gap-1.5 flex-1 w-full"
          >
            <FieldSetLabel htmlFor="registry_credentials" className="sr-only">
              Credentials
            </FieldSetLabel>
            <FieldSetSelect
              name="container_registry_credentials_id"
              value={containerRegistryCredentials}
              onValueChange={(value) => setContainerRegistryCredentials(value)}
            >
              <SelectTrigger
                id="registry_credentials"
                ref={SelectTriggerRef}
                disabled={!isEditing || serviceSourcheChange !== undefined}
                data-edited={
                  serviceSourcheChange !== undefined ? "true" : undefined
                }
                className={cn(
                  "[&_[data-item]_.flex]:flex-row [&_[data-item]_.flex]:gap-1",
                  "[&_[data-item]]:items-center [&_[data-item]_:first-child]:top-0",
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
              >
                <SelectValue placeholder="None" />
              </SelectTrigger>
              <SelectContent>
                {registries.map((registry) => {
                  const Icon = DEFAULT_REGISTRIES[registry.registry_type].Icon;
                  return (
                    <SelectItem
                      value={registry.id}
                      className="items-start [&_[data-indicator]]:relative [&_[data-indicator]]:top-0.5"
                    >
                      <div data-item className="inline-flex items-start gap-2">
                        <Icon className="relative top-0.5" />
                        <div className="flex flex-col items-start gap-0 md:flex-row md:items-center md:gap-1">
                          <span>{registry.slug}</span>
                          <span className="text-grey">{registry.username}</span>
                        </div>
                      </div>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </FieldSetSelect>
          </FieldSet>
        </fieldset>
        <div className="flex gap-4">
          {serviceSourcheChange !== undefined ? (
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
                    setContainerRegistryCredentials(
                      container_registry_credentials_id
                    );
                  });
                  if (newIsEditing) {
                    inputRef.current?.focus();
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
    </div>
  );
}
