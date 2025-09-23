import { SettingsIcon } from "lucide-react";
import { Link, href } from "react-router";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import { Card } from "~/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import type { Project } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { capitalizeText, pluralize } from "~/utils";

export type ProjectCardProps = {
  project: Project;
};

export function ProjectCard({ project }: ProjectCardProps) {
  return (
    <Card
      className={cn(
        "flex group flex-col h-[160px] gap-2",
        "rounded-2xl bg-toggle relative ring-1 ",
        "ring-transparent hover:ring-primary focus-within:ring-primary",
        "transition-colors duration-300",
        "p-4 pt-3"
      )}
    >
      <div className="flex items-center justify-between gap-2 text-lg font-semibold">
        <Link
          to={href("/project/:projectSlug/:envSlug", {
            envSlug: "production",
            projectSlug: project.slug
          })}
          className={cn("hover:underline", "after:inset-0 after:absolute")}
        >
          {capitalizeText(project.slug)}
        </Link>

        <TooltipProvider>
          <Tooltip delayDuration={0}>
            <TooltipTrigger asChild>
              <Button asChild variant="ghost" size="sm" className="w-9">
                <Link
                  to={href("/project/:projectSlug/settings", {
                    projectSlug: project.slug
                  })}
                  className="relative z-10"
                >
                  <SettingsIcon width={18} className="flex-none" />
                </Link>
              </Button>
            </TooltipTrigger>
            <TooltipContent>Go to project settings</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>

      <div className="grow flex flex-col justify-center">
        <small
          className={cn(
            "text-sm text-grey overflow-hidden h-11",
            "[-webkit-box-orient:vertical] [-webkit-line-clamp:2] [display:-webkit-box]"
          )}
        >
          {project.description ?? (
            <em className="font-mono opacity-60">{"<no description>"}</em>
          )}
        </small>
      </div>

      <StatusBadge
        color={
          project.healthy_services === project.total_services
            ? "green"
            : project.healthy_services === 0
              ? "red"
              : "yellow"
        }
      >
        <p>
          {project.healthy_services}/
          {`${project.total_services} ${pluralize("Service", project.total_services)} healthy`}
        </p>
      </StatusBadge>
    </Card>
  );
}
