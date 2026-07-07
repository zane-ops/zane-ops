import { useQuery } from "@tanstack/react-query";
import { CheckIcon, ChevronsUpDownIcon } from "lucide-react";
import { Link, href, useFetcher, useNavigate, useParams } from "react-router";
import type { Project } from "~/api/types";
import { StatusBadge } from "~/components/status-badge";
import { Button } from "~/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger
} from "~/components/ui/dropdown-menu";
import { projectQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type ProjectEnvironmentListHeaderHeaderDropdownProps = {};

export function ProjectEnvironmentListHeaderHeaderDropdown(
  props: ProjectEnvironmentListHeaderHeaderDropdownProps
) {
  const { envSlug, workspaceId, projectSlug } = useParams() as {
    workspaceId: string;
    projectSlug: string;
    envSlug: string;
  };

  const { data: project } = useQuery({
    ...projectQueries.single(workspaceId, projectSlug)
  });

  const navigate = useNavigate();

  if (!project) return;

  return (
    <div className="inline-flex items-center gap-1">
      <Button
        variant="ghost"
        asChild
        className="inline-flex gap-1.5 py-0 px-2 rounded-sm text-sm h-8"
      >
        <Link
          to={href("/:workspaceId/project/:projectSlug/:envSlug", {
            workspaceId,
            projectSlug,
            envSlug
          })}
          className={cn(
            "text-foreground"
            // envSlug === "production"
            //   ? "text-green-500 dark:text-primary"
            //   : envSlug.startsWith("preview")
            //     ? "text-link"
            //     : "text-foreground"
          )}
        >
          <div
            className={cn(
              "size-6 flex-none rounded-md flex items-center justify-center",
              envSlug === "production"
                ? "text-green-500 dark:text-primary"
                : envSlug.startsWith("preview")
                  ? "text-link"
                  : "text-foreground"
            )}
          >
            <span></span>
          </div>
          <span>{envSlug}</span>
        </Link>
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            className="inline-flex justify-center items-center gap-2 p-1 h-8 w-6"
          >
            <ChevronsUpDownIcon className="size-3.5 flex-none my-auto text-grey" />
          </Button>
        </DropdownMenuTrigger>

        <DropdownMenuContent
          align="start"
          alignOffset={0}
          className="border min-w-0 border-border rounded-lg"
        >
          <DropdownMenuGroup className="px-0.5">
            <DropdownMenuLabel>Environments</DropdownMenuLabel>
            {project.environments.map((env) => {
              return (
                <DropdownMenuItem
                  key={env.id}
                  className="flex items-start gap-2 py-2 pl-2.5 pr-3"
                  onClick={() =>
                    navigate(
                      href("/:workspaceId/project/:projectSlug/:envSlug", {
                        workspaceId,
                        projectSlug,
                        envSlug: env.name
                      })
                    )
                  }
                >
                  {/* <div
                      className={cn(
                        "size-6 flex-none rounded-md flex items-center justify-center",
                        "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                        "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
                        "border border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
                      )}
                    >
                      <span>{m.workspace.name.charAt(0).toUpperCase()}</span>
                    </div> */}

                  <div className="flex items-start gap-8 justify-between w-full">
                    <div className="flex flex-col mr-2 items-start gap-0.5">
                      <span className="font-medium">{env.name}</span>
                    </div>

                    <span className="flex size-4 items-center justify-center ml-auto flex-none py-2.5">
                      {env.name === envSlug && (
                        <CheckIcon className="size-full text-teal-600 dark:text-teal-400" />
                      )}
                    </span>
                  </div>
                </DropdownMenuItem>
              );
            })}
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
