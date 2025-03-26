import {
  CheckIcon,
  EyeIcon,
  EyeOffIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import { toast } from "sonner";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
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
import type { Service } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  type clientAction,
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceBuilderFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

type ServiceBuilderChangeNewValue = Pick<Service, "builder"> & {
  options: Service["dockerfile_builder_options"];
};

export function ServiceBuilderForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceBuilderFormProps) {
  const { fetcher, data, reset } = useFetcherWithCallbacks({});
  const isPending = fetcher.state !== "idle";
  const [isEditing, setIsEditing] = React.useState(false);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const serviceBuilderChange = service.unapplied_changes.find(
    (change) => change.field === "builder"
  ) as
    | {
        new_value: ServiceBuilderChangeNewValue;
        id: string;
      }
    | undefined;

  const serviceBuilder =
    serviceBuilderChange?.new_value.builder ?? service.builder!;

  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form method="post" className="flex flex-col gap-4 w-full">
        <input type="hidden" name="change_field" value="git_source" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input
          type="hidden"
          name="change_id"
          value={serviceBuilderChange?.id}
        />

        <FieldSet
          name="repository_url"
          className="flex flex-col gap-1.5 flex-1"
          required
          errors={errors.new_value?.repository_url}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Repository URL&nbsp;
          </FieldSetLabel>
          <div className="relative">
            <FieldSetInput
              ref={inputRef}
              disabled={!isEditing || serviceBuilderChange !== undefined}
              placeholder="ex: https://github.com/zane-ops/zane-ops"
              defaultValue={serviceBuilder}
              data-edited={
                serviceBuilderChange !== undefined ? "true" : undefined
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
                <span className="text-grey">{repoUrl.origin}</span>
                <span>{repoUrl.pathname}</span>
              </span>
            )}
          </div>
        </FieldSet>

        <div className="flex flex-col md:items-center gap-1.5 md:flex-row md:gap-3 w-full">
          <FieldSet
            name="branch_name"
            className="flex flex-col gap-1.5 flex-1"
            required
            errors={errors.new_value?.branch_name}
          >
            <FieldSetLabel className="dark:text-card-foreground">
              Branch name&nbsp;
            </FieldSetLabel>
            <div className="relative">
              <FieldSetInput
                disabled={!isEditing || serviceSourceChange !== undefined}
                placeholder="ex: main"
                defaultValue={serviceBranch}
                data-edited={
                  serviceSourceChange !== undefined ? "true" : undefined
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
                  <span>{serviceBranch}</span>
                </span>
              )}
            </div>
          </FieldSet>

          <FieldSet
            name="commit_sha"
            className="flex flex-col gap-1.5 flex-1"
            required
            errors={errors.new_value?.commit_sha}
          >
            <FieldSetLabel className="dark:text-card-foreground inline-flex items-center gap-0.5">
              Commit SHA&nbsp;
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger>
                    <InfoIcon size={15} />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-64">
                    <ul className="list-disc px-4 py-1">
                      <li>
                        You can use <Code>HEAD</Code> to reference the latest
                        commit of the branch
                      </li>
                      <li>
                        You can use either the short commit (7 chars minimum),
                        or the long commit sha
                      </li>
                    </ul>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </FieldSetLabel>
            <div className="relative">
              <FieldSetInput
                disabled={!isEditing || serviceSourceChange !== undefined}
                placeholder="ex: HEAD"
                defaultValue={serviceCommitSha}
                data-edited={
                  serviceSourceChange !== undefined ? "true" : undefined
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
                  <span>{serviceCommitSha}</span>
                </span>
              )}
            </div>
          </FieldSet>
        </div>
        <div className="flex gap-4">
          {serviceSourceChange !== undefined ? (
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
                  });
                  if (newIsEditing) {
                    inputRef.current?.focus();
                  }
                  reset();
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
