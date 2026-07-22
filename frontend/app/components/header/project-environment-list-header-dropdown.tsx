import { useQuery } from "@tanstack/react-query";
import { CheckIcon, ChevronsUpDownIcon, NetworkIcon } from "lucide-react";
import { Link, href, useNavigate, useParams } from "react-router";
import type { Project } from "~/api/types";
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
import { useCurrentWorkspace } from "~/lib/workspace-store";

export type ProjectEnvironmentListHeaderHeaderDropdownProps = {
  currentProject?: Project;
};

export function ProjectEnvironmentListHeaderHeaderDropdown(
  props: ProjectEnvironmentListHeaderHeaderDropdownProps
) {
  const workspaceId = useCurrentWorkspace().id;
  const { envSlug, projectSlug } = useParams() as {
    projectSlug: string;
    envSlug: string;
  };

  const { data: project } = useQuery({
    ...projectQueries.single(workspaceId, projectSlug),
    initialData: props.currentProject
  });

  const navigate = useNavigate();

  if (!project) return;

  return (
    <div className="inline-flex items-center gap-1">
      <Button
        variant="ghost"
        asChild
        className="inline-flex gap-1.5 py-0 px-2 rounded-sm text-sm h-8 text-foreground"
      >
        <Link
          to={href("/workspace/project/:projectSlug/:envSlug", {
            projectSlug,
            envSlug
          })}
        >
          <div
            className={cn(
              "size-6 flex-none rounded-md flex items-center justify-center",
              envSlug === "production"
                ? "text-teal-500 dark:text-primary"
                : envSlug.startsWith("preview")
                  ? "text-link"
                  : "text-foreground"
            )}
          >
            <NetworkIcon size={16} className="flex-none" />
          </div>
          <p
            className={cn(
              "text-foreground whitespace-nowrap overflow-x-hidden text-ellipsis",
              "max-w-16 md:max-w-24 xl:max-w-32"
            )}
          >
            {envSlug}
          </p>
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
                      href("/workspace/project/:projectSlug/:envSlug", {
                        projectSlug,
                        envSlug: env.name
                      })
                    )
                  }
                >
                  <div
                    className={cn(
                      "flex-none rounded-md flex items-center justify-center relative top-0.5",
                      env.name === "production"
                        ? "text-teal-500 dark:text-primary"
                        : env.name.startsWith("preview")
                          ? "text-link"
                          : "text-foreground"
                    )}
                  >
                    <NetworkIcon size={16} className="flex-none" />
                  </div>

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
