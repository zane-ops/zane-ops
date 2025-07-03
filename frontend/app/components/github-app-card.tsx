import {
  ArrowBigDownDashIcon,
  CheckIcon,
  ClockIcon,
  ExternalLinkIcon,
  GithubIcon,
  LoaderIcon,
  PenLineIcon,
  UnplugIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { useFetcher } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button, SubmitButton } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import { FieldSet, FieldSetInput } from "~/components/ui/fieldset";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { GitApp } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/settings/github-app-details";
import { formattedDate } from "~/utils";

export type GithubAppCardProps = {
  app: NonNullable<GitApp["github"]>;
  children: React.ReactNode;
};

export function GithubAppCard({ app, children }: GithubAppCardProps) {
  const testConnectionFetcher = useFetcher<typeof clientAction>();
  const renameFetcher = useFetcher<typeof clientAction>();
  const isRenaming = renameFetcher.state !== "idle";
  const [isEditing, setIsEditing] = React.useState(false);
  const [data, setData] = React.useState(renameFetcher.data);
  const errors = getFormErrorsFromResponseData(data?.errors);
  const inputRef = React.useRef<React.ComponentRef<"input">>(null);

  React.useEffect(() => {
    setData(renameFetcher.data);

    if (renameFetcher.state === "idle" && renameFetcher.data?.data) {
      setIsEditing(false);
    }
  }, [renameFetcher.state, renameFetcher.data]);

  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex flex-col items-start md:flex-row md:items-center bg-toggle">
        <div>
          <div className=" flex-col gap-2 items-center text-grey hidden md:flex">
            <GithubIcon size={30} className="flex-none" />
            <Badge variant="outline" className="text-grey">
              app
            </Badge>
          </div>
        </div>
        <div className="flex flex-col flex-1 gap-0.5">
          <renameFetcher.Form
            className={cn(
              "flex group gap-2",
              isEditing ? "items-start" : "items-center"
            )}
            method="post"
            action={`./github/${app.id}`}
          >
            <input type="hidden" name="intent" value="rename_github_app" />
            {isEditing ? (
              <>
                <FieldSet name="name" errors={errors.name}>
                  <FieldSetInput
                    ref={inputRef}
                    placeholder="github app name"
                    defaultValue={app.name}
                  />
                </FieldSet>
                <SubmitButton
                  isPending={isRenaming}
                  variant="outline"
                  className="bg-inherit"
                  name="intent"
                  value="update-slug"
                  size="sm"
                >
                  {isRenaming ? (
                    <>
                      <LoaderIcon className="animate-spin" size={15} />
                      <span className="sr-only">Submiting...</span>
                    </>
                  ) : (
                    <>
                      <CheckIcon size={15} className="flex-none" />
                      <span className="sr-only">Submit</span>
                    </>
                  )}
                </SubmitButton>
                <Button
                  onClick={(ev) => {
                    ev.currentTarget.form?.reset();
                    setIsEditing(false);
                    setData(undefined);
                  }}
                  variant="outline"
                  className="bg-inherit"
                  type="reset"
                  size="sm"
                >
                  <XIcon size={15} className="flex-none" />
                  <span className="sr-only">Cancel</span>
                </Button>
              </>
            ) : (
              <>
                <h3 className="text-lg font-medium">{app.name}</h3>
                <Button
                  type="button"
                  className="opacity-100 md:opacity-0 focus:opacity-100 group-hover:opacity-100"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    flushSync(() => setIsEditing(true));
                    inputRef.current?.focus();
                  }}
                >
                  <PenLineIcon size={15} className="flex-none" />
                  <span className="sr-only">Rename app</span>
                </Button>
              </>
            )}
          </renameFetcher.Form>
          <div className="text-sm text-link flex items-center gap-1">
            <ExternalLinkIcon size={15} className="flex-none" />
            <a href={app.app_url} className="break-all" target="_blank">
              {app.app_url}
            </a>
          </div>
          <div className="text-grey text-sm flex items-center gap-1">
            <ClockIcon size={15} className="flex-none" />
            <span>
              Added on&nbsp;
              <time dateTime={app.created_at}>
                {formattedDate(app.created_at)}
              </time>
            </span>
          </div>
        </div>
        <testConnectionFetcher.Form
          id={`test-connection-${app.id}`}
          className="hidden"
          method="post"
          action={`./github/${app.id}`}
        />
        <div className="flex items-center gap-1">
          <TooltipProvider>
            {!app.is_installed ? (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button size="sm" variant="ghost" asChild>
                    <Button asChild variant="ghost">
                      <a
                        href={`${app.app_url}/installations/new?state=install:${app.id}`}
                      >
                        <ArrowBigDownDashIcon size={15} />
                        <span className="sr-only">
                          Install application on GitHub
                        </span>
                      </a>
                    </Button>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Install application on GitHub</TooltipContent>
              </Tooltip>
            ) : (
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <SubmitButton
                    isPending={testConnectionFetcher.state !== "idle"}
                    form={`test-connection-${app.id}`}
                    size="sm"
                    variant="ghost"
                    name="intent"
                    value="test_github_app_connection"
                  >
                    {testConnectionFetcher.state !== "idle" ? (
                      <>
                        <LoaderIcon className="animate-spin" size={15} />
                        <span className="sr-only">Testing...</span>
                      </>
                    ) : (
                      <>
                        <UnplugIcon size={15} />
                        <span className="sr-only">
                          Test GitHub App installation
                        </span>
                      </>
                    )}
                  </SubmitButton>
                </TooltipTrigger>
                <TooltipContent>Test GitHub App installation</TooltipContent>
              </Tooltip>
            )}
          </TooltipProvider>
          {children}
        </div>
      </CardContent>
    </Card>
  );
}
