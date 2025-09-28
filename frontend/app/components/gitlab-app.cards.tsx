import {
  ChevronRightIcon,
  ClockIcon,
  GitlabIcon,
  HashIcon,
  LoaderIcon,
  PenLineIcon,
  RefreshCcwIcon,
  UnplugIcon
} from "lucide-react";
import * as React from "react";
import { Link, useFetcher } from "react-router";
import { Badge } from "~/components/ui/badge";
import { SubmitButton } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { GitlabApp } from "~/lib/queries";
import { cn } from "~/lib/utils";
import type { clientAction } from "~/routes/settings/github-app-details";
import { formattedDate } from "~/utils";

export type GitlabAppCardProps = {
  app: GitlabApp;
  children: React.ReactNode;
};

export function GitlabAppCard({ app, children }: GitlabAppCardProps) {
  const testConnectionFetcher = useFetcher<typeof clientAction>();
  const syncReposFetcher = useFetcher<typeof clientAction>();

  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex flex-col items-start md:flex-row md:items-center bg-toggle">
        <div className="flex-none flex-col gap-2 items-center text-grey hidden md:flex">
          <GitlabIcon size={30} className="flex-none" />
          <Badge variant="outline" className="text-grey">
            app
          </Badge>
        </div>
        <div className="flex flex-col flex-1 gap-0.5 shrink min-w-0 w-full">
          <div className="relative">
            <Link
              to={`./gitlab/${app.id}`}
              className={cn(
                "after:absolute after:inset-0",
                "text-lg font-medium hover:underline flex items-center gap-2 ",
                "group"
              )}
            >
              <span className="opacity-100">{app.name}</span>
              <PenLineIcon
                size={15}
                className={cn(
                  "flex-none",
                  "opacity-100 md:opacity-0 group-hover:opacity-100 group-focus:opacity-100"
                )}
              />
              <span className="sr-only">Rename app</span>
            </Link>
          </div>
          <div className="text-sm text-grey flex items-center gap-1 w-full max-w-full">
            <HashIcon size={15} className="flex-none" />
            <p className="truncate">{app.app_id}</p>
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
          action={`./gitlab/${app.id}`}
        />
        <syncReposFetcher.Form
          id={`sync-repos-${app.id}`}
          className="hidden"
          method="post"
          action={`./gitlab/${app.id}`}
        />
        <div className="flex items-center gap-1 flex-none">
          <TooltipProvider>
            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <SubmitButton
                  isPending={syncReposFetcher.state !== "idle"}
                  form={`sync-repos-${app.id}`}
                  size="sm"
                  variant="ghost"
                  name="intent"
                  value="sync_gitlab_repositories"
                >
                  {syncReposFetcher.state !== "idle" ? (
                    <>
                      <LoaderIcon className="animate-spin" size={15} />
                      <span className="sr-only">Synching...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCcwIcon size={15} />
                      <span className="sr-only">Synchronize repositories</span>
                    </>
                  )}
                </SubmitButton>
              </TooltipTrigger>
              <TooltipContent>Synchronize repositories</TooltipContent>
            </Tooltip>

            <Tooltip delayDuration={0}>
              <TooltipTrigger asChild>
                <SubmitButton
                  isPending={testConnectionFetcher.state !== "idle"}
                  form={`test-connection-${app.id}`}
                  size="sm"
                  variant="ghost"
                  name="intent"
                  value="test_gitlab_app_connection"
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
                        Test Gitlab App installation
                      </span>
                    </>
                  )}
                </SubmitButton>
              </TooltipTrigger>
              <TooltipContent>Test Gitlab App installation</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          {children}
        </div>
      </CardContent>
    </Card>
  );
}

export type GitlabAppCardLinkProps = {
  app: GitlabApp;
  parent_id: string;
};
export function GitlabAppCardLink({ app, parent_id }: GitlabAppCardLinkProps) {
  return (
    <Card>
      <CardContent
        className={cn(
          "rounded-md p-4 gap-4 flex items-center group w-full",
          "border-gray-600 bg-gray-600/10",
          "relative hover:bg-muted"
        )}
      >
        <div>
          <div className="flex flex-col gap-2 items-center text-grey">
            <GitlabIcon size={30} className="flex-none" />
            <Badge variant="outline" className="text-grey">
              app
            </Badge>
          </div>
        </div>

        <div className="flex flex-col flex-1 gap-0.5">
          <h3 className="text-lg font-medium">
            <Link
              to={`./${parent_id}`}
              className="before:absolute before:inset-0"
            >
              {app.name}
            </Link>
          </h3>
          <div className="text-grey text-sm flex items-center gap-1">
            <ClockIcon size={15} className="flex-none hidden sm:block" />
            <span>
              Added on&nbsp;
              <time dateTime={app.created_at}>
                {formattedDate(app.created_at)}
              </time>
            </span>
          </div>
        </div>

        <div className="flex items-center px-4">
          <ChevronRightIcon size={18} className="text-grey flex-none" />
        </div>
      </CardContent>
    </Card>
  );
}
