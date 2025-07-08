import {
  CheckIcon,
  ClockIcon,
  GitlabIcon,
  HashIcon,
  LoaderIcon,
  PenLineIcon,
  UnplugIcon,
  XIcon
} from "lucide-react";
import * as React from "react";
import { flushSync } from "react-dom";
import { Link, useFetcher } from "react-router";
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
import type { GitlabApp } from "~/lib/queries";
import { cn, getFormErrorsFromResponseData } from "~/lib/utils";
import type { clientAction } from "~/routes/settings/github-app-details";
import { formattedDate } from "~/utils";

export type GitlabAppCardProps = {
  app: GitlabApp;
  children: React.ReactNode;
};

export function GitlabAppCard({ app, children }: GitlabAppCardProps) {
  const testConnectionFetcher = useFetcher<typeof clientAction>();

  return (
    <Card>
      <CardContent className="rounded-md p-4 gap-4 flex flex-col items-start md:flex-row md:items-center bg-toggle">
        <div>
          <div className=" flex-col gap-2 items-center text-grey hidden md:flex">
            <GitlabIcon size={30} className="flex-none" />
            <Badge variant="outline" className="text-grey">
              app
            </Badge>
          </div>
        </div>
        <div className="flex flex-col flex-1 gap-0.5">
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
          <div className="text-sm text-grey flex items-center gap-1">
            <HashIcon size={15} className="flex-none" />
            {app.app_id}
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
        <div className="flex items-center gap-1">
          <TooltipProvider>
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
