import {
  CheckIcon,
  InfoIcon,
  LoaderIcon,
  PencilLineIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher, useNavigate } from "react-router";
import { Button, SubmitButton } from "~/components/ui/button";
import {
  FieldSet,
  FieldSetCheckbox,
  FieldSetErrors,
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
  type clientAction,
  useServiceQuery
} from "~/routes/services/settings/services-settings";

export type ServiceAutoDeployFormProps = {
  service_slug: string;
  project_slug: string;
  env_slug: string;
};

export function ServiceAutoDeployForm({
  project_slug,
  service_slug,
  env_slug
}: ServiceAutoDeployFormProps) {
  const [isEditing, setIsEditing] = React.useState(false);
  const fetcher = useFetcher<typeof clientAction>();

  const isPending = fetcher.state !== "idle";
  const [data, setData] = React.useState(fetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);

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
          "repository_url" | "branch_name" | "commit_sha" | "git_app"
        >;
        id: string;
      }
    | undefined;
  const serviceGitApp = serviceSourceChange
    ? serviceSourceChange.new_value.git_app
    : service.git_app;

  const [autoDeployEnabled, setAutoDeployEnabled] = React.useState(
    service.auto_deploy_enabled
  );

  React.useEffect(() => {
    setData(fetcher.data);

    if (fetcher.state === "idle" && fetcher.data?.data?.slug) {
      setIsEditing(false);
    }
  }, [fetcher.state, fetcher.data]);

  console.log({
    autoDeployEnabled
  });
  if (!serviceGitApp) {
    // Hide in case the git app is non existent
    return null;
  }

  return (
    <div className="w-full max-w-4xl">
      <fetcher.Form method="post" className="flex flex-col gap-4 w-full">
        <h3 className="text-lg">Auto deploy options</h3>
        <p className="text-grey">Only available when you select a Git app</p>

        <FieldSet
          name="auto_deploy_enabled"
          className="flex-1 inline-flex gap-2 flex-col"
          errors={errors.auto_deploy_enabled}
        >
          <div className="inline-flex gap-2 items-center">
            <FieldSetCheckbox
              disabled={!isEditing}
              defaultChecked={autoDeployEnabled}
              checked={autoDeployEnabled}
              onCheckedChange={(checked) => {
                console.log({
                  checked
                });
                setAutoDeployEnabled(Boolean(checked));
              }}
            />

            <FieldSetLabel className="inline-flex gap-1 items-center">
              <span>Auto-deploy enabled ?</span>
              <TooltipProvider>
                <Tooltip delayDuration={0}>
                  <TooltipTrigger>
                    <InfoIcon size={15} />
                  </TooltipTrigger>
                  <TooltipContent className="max-w-48">
                    Wether or not to trigger a new deployment when you make a
                    push to the repository linked to this service.
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </FieldSetLabel>
          </div>
        </FieldSet>

        {autoDeployEnabled && (
          <div className="flex flex-col gap-4 pl-4">
            <FieldSet
              name="cleanup_queue_on_deploy"
              className="flex-1 inline-flex gap-2 flex-col"
              errors={errors.cleanup_queue_on_deploy}
            >
              <div className="inline-flex gap-2 items-center">
                <FieldSetCheckbox
                  disabled={!isEditing}
                  defaultChecked={service.cleanup_queue_on_deploy}
                />

                <FieldSetLabel className="inline-flex gap-1 items-center">
                  <span>Cleanup Queue on deploy ?</span>
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger>
                        <InfoIcon size={15} />
                      </TooltipTrigger>
                      <TooltipContent className="max-w-48">
                        If checked, this will stop and cancel all previous
                        running deployments when you push a new commit.
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </FieldSetLabel>
              </div>
            </FieldSet>

            <FieldSet
              name="watch_paths"
              errors={errors.watch_paths}
              className="flex flex-col gap-1.5 flex-1"
            >
              <FieldSetLabel htmlFor="slug">
                Watch paths
                <TooltipProvider>
                  <Tooltip delayDuration={0}>
                    <TooltipTrigger>
                      <InfoIcon size={15} />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-48">
                      Whenever any of the changes in the paths below changes,
                      trigger a new deployment.
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </FieldSetLabel>
              <div className="relative">
                <FieldSetInput
                  placeholder={
                    !isEditing && !service.watch_paths?.trim()
                      ? "<empty>"
                      : "*/*"
                  }
                  defaultValue={service.watch_paths}
                  disabled={!isEditing}
                  className={cn(
                    "disabled:placeholder-shown:font-mono disabled:bg-muted",
                    "disabled:border-transparent disabled:opacity-100"
                  )}
                />
              </div>
            </FieldSet>
          </div>
        )}

        <div className="flex gap-4">
          {isEditing && (
            <SubmitButton
              isPending={isPending}
              variant="secondary"
              className="self-start"
              name="intent"
              value="update-auto-deploy"
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
        </div>
      </fetcher.Form>
    </div>
  );
}
