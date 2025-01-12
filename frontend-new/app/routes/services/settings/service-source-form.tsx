import {
  CheckIcon,
  EyeIcon,
  EyeOffIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
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
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceFormProps = {
  service_slug: string;
  project_slug: string;
};

export function ServiceSourceForm({
  service_slug,
  project_slug
}: ServiceFormProps) {
  const fetcher = useFetcher<typeof clientAction>();
  const isPending = fetcher.state !== "idle";

  const [data, setData] = React.useState(fetcher.data);
  const [isEditing, setIsEditing] = React.useState(false);
  const [isPasswordShown, setIsPasswordShown] = React.useState(false);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const { data: service } = useServiceQuery({ project_slug, service_slug });

  React.useEffect(() => {
    setData(fetcher.data);
    if (fetcher.state === "idle" && fetcher.data) {
      if (!fetcher.data.errors) {
        setIsEditing(false);
        setIsPasswordShown(false);
      }
    }
  }, [fetcher.state, fetcher.data]);

  const serviceSourcheChange = service.unapplied_changes.find(
    (change) => change.field === "source"
  ) as
    | { new_value: Pick<DockerService, "image" | "credentials">; id: string }
    | undefined;

  const serviceImage = serviceSourcheChange?.new_value.image ?? service.image!;
  const imageParts = serviceImage.split(":");
  const tag = imageParts.length > 1 ? imageParts.pop() : "latest";
  const image = imageParts.join(":");

  const credentials =
    serviceSourcheChange?.new_value.credentials ?? service.credentials;

  const errors = getFormErrorsFromResponseData(data?.errors);

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

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form method="post" className="flex flex-col gap-4 w-full">
        <input type="hidden" name="change_field" value="source" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input
          type="hidden"
          name="change_id"
          value={serviceSourcheChange?.id}
        />
        <fieldset className="flex flex-col gap-1.5 flex-1">
          <label htmlFor="image">Source Image</label>
          <div className="relative">
            <Input
              id="image"
              name="image"
              ref={inputRef}
              disabled={!isEditing || serviceSourcheChange !== undefined}
              placeholder="image"
              defaultValue={serviceImage}
              aria-labelledby="image-error"
              aria-invalid={Boolean(errors.new_value?.image)}
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
            {!isEditing && (
              <span className="absolute inset-y-0 left-3 flex items-center pr-2 text-sm">
                {image}
                <span className="text-grey">:{tag}</span>
              </span>
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
            If your service pulls private Docker images from a registry, specify
            the information below.
          </p>

          <label
            className="text-muted-foreground"
            htmlFor="credentials.username"
          >
            Username for registry
          </label>
          <div className="flex flex-col gap-1">
            <Input
              placeholder={!isEditing ? "<empty>" : "username"}
              name="credentials.username"
              id="credentials.username"
              disabled={!isEditing || serviceSourcheChange !== undefined}
              defaultValue={credentials?.username}
              data-edited={
                serviceSourcheChange !== undefined ? "true" : undefined
              }
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100 disabled:select-none"
              )}
              aria-invalid={Boolean(errors.new_value?.credentials?.username)}
              aria-labelledby="credentials.username-error"
            />
            {errors.new_value?.credentials?.username && (
              <span
                id="credentials.username-error"
                className="text-red-500 text-sm"
              >
                {errors.new_value?.credentials?.username}
              </span>
            )}
          </div>

          <label
            className="text-muted-foreground"
            htmlFor="credentials.password"
          >
            Password for registry
          </label>
          <div className="flex gap-2 items-start">
            <div className="inline-flex flex-col gap-1 flex-1">
              <Input
                placeholder={!isEditing ? "<empty>" : "*******"}
                disabled={!isEditing || serviceSourcheChange !== undefined}
                type={isPasswordShown ? "text" : "password"}
                defaultValue={credentials?.password}
                name="credentials.password"
                id="credentials.password"
                data-edited={
                  serviceSourcheChange !== undefined ? "true" : undefined
                }
                className={cn(
                  "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                  "data-[edited]:dark:disabled:bg-secondary-foreground",
                  "disabled:border-transparent disabled:opacity-100"
                )}
                aria-invalid={Boolean(errors.new_value?.credentials?.password)}
                aria-labelledby="credentials.password-error"
              />
              {errors.new_value?.credentials?.password && (
                <span
                  id="credentials.username-error"
                  className="text-red-500 text-sm"
                >
                  {errors.new_value?.credentials?.password}
                </span>
              )}
            </div>

            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => setIsPasswordShown(!isPasswordShown)}
                    className="p-4"
                  >
                    {isPasswordShown ? (
                      <EyeOffIcon size={15} className="flex-none" />
                    ) : (
                      <EyeIcon size={15} className="flex-none" />
                    )}
                    <span className="sr-only">
                      {isPasswordShown ? "Hide" : "Show"} password
                    </span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {isPasswordShown ? "Hide" : "Show"} password
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
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
                    <span>Reverting...</span>
                  </>
                ) : (
                  <>
                    <Undo2Icon size={15} className="flex-none" />
                    <span>Revert change</span>
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
