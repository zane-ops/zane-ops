import {
  ArrowBigDownDashIcon,
  ChevronRightIcon,
  ClockIcon,
  ExternalLinkIcon,
  LoaderIcon,
  PenLineIcon,
  UnplugIcon
} from "lucide-react";
import type * as React from "react";
import { Link, useFetcher } from "react-router";
import type { GithubApp } from "~/api/types";
import { GithubLogo } from "~/components/github-logo";
import { Badge } from "~/components/ui/badge";
import { Button, SubmitButton } from "~/components/ui/button";
import { Card, CardContent } from "~/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn, formattedDate } from "~/lib/utils";
import type { clientAction } from "~/routes/settings/github-app-details";

export type GithubAppCardProps = {
  app: GithubApp;
  children: React.ReactNode;
};

export function GithubAppCard({ app, children }: GithubAppCardProps) {
  const testConnectionFetcher = useFetcher<typeof clientAction>();

  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex flex-col items-start md:flex-row md:items-center bg-toggle">
        <div className=" flex-col gap-2 items-center text-grey hidden md:flex">
          <GithubLogo className="flex-none size-7.5" />
          <Badge variant="outline" className="text-grey">
            app
          </Badge>
        </div>
        <div className="flex flex-col flex-1 gap-0.5">
          <div className="relative">
            <Link
              to={`./github/${app.id}`}
              className={cn(
                "after:absolute after:inset-0",
                "text-lg font-medium hover:underline flex items-center gap-2",
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
              <Button
                asChild
                variant="default"
                className="inline-flex gap-0.5 items-center"
              >
                <a
                  href={`${app.app_url}/installations/new?state=install:${app.id}`}
                >
                  <span>Install on GitHub</span>
                  <ArrowBigDownDashIcon size={15} />
                </a>
              </Button>
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

export type GithubAppCardLinkProps = {
  app: GithubApp;
  parent_id: string;
};
export function GithubAppCardLink({ app, parent_id }: GithubAppCardLinkProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Card>
            <CardContent
              className={cn(
                "rounded-md p-4 gap-4 flex items-center group flex-wrap w-full",
                "border-gray-600 bg-gray-600/10",
                "relative hover:bg-muted",
                !app.is_installed && "opacity-50 hover:bg-gray-600/10"
              )}
            >
              <div>
                <div className="flex flex-col gap-2 items-center text-grey">
                  <GithubLogo className="flex-none size-7.5" />
                  <Badge variant="outline" className="text-grey">
                    app
                  </Badge>
                </div>
              </div>

              <div className="flex flex-col flex-1 gap-0.5">
                <h3 className="text-lg font-medium">
                  {app.is_installed ? (
                    <Link
                      to={`./${parent_id}`}
                      className="before:absolute before:inset-0"
                    >
                      {app.name}
                    </Link>
                  ) : (
                    <>{app.name}</>
                  )}
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
        </TooltipTrigger>
        {!app.is_installed && (
          <TooltipContent side="bottom">
            This app needs to be installed before it can be used
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  );
}
