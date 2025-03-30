import {
  CheckIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  Undo2Icon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { Code } from "~/components/code";
import { Button } from "~/components/ui/button";
import { SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetInput,
  FieldSetLabel
} from "~/components/ui/fieldset";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { Service } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import {
  useFetcherWithCallbacks,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceGitSourceFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

export function ServiceGitSourceForm({
  service_slug,
  project_slug,
  env_slug
}: ServiceGitSourceFormProps) {
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
    onSuccess(data) {
      setIsEditing(false);
    }
  });
  const isPending = fetcher.state !== "idle";
  const [isEditing, setIsEditing] = React.useState(false);

  const inputRef = React.useRef<React.ComponentRef<"input">>(null);
  const formRef = React.useRef<React.ComponentRef<"form">>(null);

  const { data: service } = useServiceQuery({
    project_slug,
    service_slug,
    env_slug
  });

  const serviceSourceChange = service.unapplied_changes.find(
    (change) => change.field === "git_source"
  ) as
    | {
        new_value: Pick<
          Service,
          "repository_url" | "branch_name" | "commit_sha"
        >;
        id: string;
      }
    | undefined;

  const serviceRepo =
    serviceSourceChange?.new_value.repository_url ?? service.repository_url!;
  const serviceBranch =
    serviceSourceChange?.new_value.branch_name ?? service.branch_name!;
  const serviceCommitSha =
    serviceSourceChange?.new_value.commit_sha ?? service.commit_sha!;

  const repoUrl = new URL(serviceRepo);
  const errors = getFormErrorsFromResponseData(data?.errors);

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form
        method="post"
        className="flex flex-col gap-4 w-full"
        ref={formRef}
      >
        <input type="hidden" name="change_field" value="git_source" />
        <input type="hidden" name="change_type" value="UPDATE" />
        <input type="hidden" name="change_id" value={serviceSourceChange?.id} />

        <FieldSet
          name="repository_url"
          className="flex flex-col gap-1.5 flex-1"
          required
          errors={errors.new_value?.repository_url}
        >
          <FieldSetLabel className="dark:text-card-foreground">
            Repository URL
          </FieldSetLabel>
          <div className="relative">
            <FieldSetInput
              ref={inputRef}
              placeholder="ex: https://github.com/zane-ops/zane-ops"
              defaultValue={serviceRepo}
              data-edited={
                serviceSourceChange !== undefined ? "true" : undefined
              }
              disabled={!isEditing || serviceSourceChange !== undefined}
              className={cn(
                "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
                "data-[edited]:dark:disabled:bg-secondary-foreground",
                "disabled:border-transparent disabled:opacity-100",
                "disabled:text-transparent disabled:select-none"
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

        <div className="flex flex-col md:items-start gap-1.5 md:flex-row md:gap-3 w-full">
          <FieldSet
            name="branch_name"
            className="flex flex-col gap-1.5 flex-1"
            required
            errors={errors.new_value?.branch_name}
          >
            <FieldSetLabel>Branch name</FieldSetLabel>
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
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
            </div>
          </FieldSet>

          <FieldSet
            name="commit_sha"
            className="flex flex-col gap-1.5 flex-1"
            required
            errors={errors.new_value?.commit_sha}
          >
            <FieldSetLabel className="inline-flex items-center gap-0.5">
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
                  "disabled:border-transparent disabled:opacity-100"
                )}
              />
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
