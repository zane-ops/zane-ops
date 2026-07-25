import { useQuery } from "@tanstack/react-query";
import { Command as CommandPrimitive } from "cmdk";
import {
  CheckIcon,
  ChevronsUpDownIcon,
  PlusIcon,
  SearchIcon
} from "lucide-react";
import * as React from "react";
import { Link, href, useNavigate, useParams } from "react-router";
import type { Project } from "~/api/types";
import { Button } from "~/components/ui/button";
import {
  Command,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandSeparator
} from "~/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from "~/components/ui/popover";
import { projectQueries } from "~/lib/queries";
import { useDeviceSize } from "~/lib/use-device-size";
import { cn, durationToMs, hasMinRole, stringToColor } from "~/lib/utils";
import {
  useCurrentWorkspace,
  useCurrentWorkspaceMembership
} from "~/lib/workspace-store";

export type WorkspaceProjectListHeaderDropdownProps = {
  projectList: Project[];
};

export function WorkspaceProjectListHeaderDropdown(
  props: WorkspaceProjectListHeaderDropdownProps
) {
  const deviceSize = useDeviceSize();
  const workspaceId = useCurrentWorkspace().id;
  const params = useParams() as { projectSlug: string };
  const membership = useCurrentWorkspaceMembership();

  const { data: projectList } = useQuery({
    ...projectQueries.list({
      workspaceId,
      refetchInterval: durationToMs(5, "minutes")
    }),
    initialData: props.projectList
  });
  const { data: current } = useQuery({
    ...projectQueries.single(workspaceId, params.projectSlug)
  });

  const navigate = useNavigate();

  const [query, setQuery] = React.useState("");
  const [isPopoverOpen, setPopoverOpen] = React.useState(false);

  if (!current) return null;

  const projectColor = stringToColor(current.slug);

  return (
    <div className="inline-flex items-center gap-1">
      <Button
        variant="ghost"
        asChild
        className="inline-flex gap-1.5 px-2 py-1 rounded-sm text-sm h-8"
      >
        <Link
          to={href("/workspace/project/:projectSlug/:envSlug", {
            projectSlug: params.projectSlug,
            envSlug: "production"
          })}
        >
          <div
            style={
              {
                "--color-light": projectColor.light,
                "--color-dark": projectColor.dark
              } as React.CSSProperties
            }
            className={cn(
              "size-6 flex-none rounded-md flex items-center justify-center",
              "text-[var(--color-light)] dark:text-[var(--color-dark)]",
              "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
              "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
            )}
          >
            <span>{current.slug.charAt(0).toUpperCase()}</span>
          </div>
          <p
            className={cn(
              "text-foreground whitespace-nowrap overflow-x-hidden text-ellipsis",
              "max-w-16 md:max-w-24 xl:max-w-32"
            )}
          >
            {current.slug}
          </p>
        </Link>
      </Button>

      <Popover open={isPopoverOpen} onOpenChange={setPopoverOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="ghost"
            className="inline-flex justify-center items-center gap-2 p-1 h-8 w-6"
          >
            <ChevronsUpDownIcon className="size-3.5 flex-none my-auto text-grey" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          className={cn(
            "w-auto p-0 z-60 shadow-md rounded-lg",
            "[&_[data-slot='command-list-wrapper']_*]:static",
            "[&_[data-slot='command-input-wrapper']]:px-2"
          )}
          align={deviceSize === "phone" ? "end" : "start"}
        >
          <Command
            loop
            filter={(value, query) => {
              const search = query;

              if (
                value === "CREATE_PROJECT" ||
                value.toLowerCase().includes(search.trim().toLowerCase())
              ) {
                return 1;
              }
              return 0;
            }}
          >
            <div className="flex px-3 py-3.5 items-center gap-1">
              <SearchIcon className="size-4 flex-none text-grey" />
              <CommandPrimitive.Input
                placeholder="Search projects"
                className="text-sm bg-inherit focus-visible:outline-hidden px-2 w-42"
                onValueChange={setQuery}
                value={query}
              />
            </div>
            <hr className="w-full border-border" />
            <CommandList className="max-h-max px-0 flex flex-col gap-2 min-w-32 md:min-w-42 w-full bg-transparent border-none">
              <CommandGroup
                heading="projects"
                className="max-h-[300px] overflow-y-auto overflow-x-clip"
              >
                {projectList.map((project) => {
                  const color = stringToColor(project.slug);
                  const isSelected = project.slug === current.slug;

                  return (
                    <CommandItem
                      key={project.id}
                      value={project.slug}
                      onSelect={() => {
                        navigate(
                          href("/workspace/project/:projectSlug/:envSlug", {
                            projectSlug: project.slug,
                            envSlug: "production"
                          })
                        );
                        setQuery("");
                        setPopoverOpen(false);
                      }}
                      className="cursor-pointer flex gap-1.5"
                    >
                      <div
                        style={
                          {
                            "--color-light": color.light,
                            "--color-dark": color.dark
                          } as React.CSSProperties
                        }
                        className={cn(
                          "size-6 flex-none rounded-md flex items-center justify-center",
                          "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                          "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
                          "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10"
                        )}
                      >
                        <span>{project.slug.charAt(0).toUpperCase()}</span>
                      </div>
                      <div className="flex items-center justify-between w-full gap-4">
                        <span className="whitespace-nowrap">
                          {project.slug}
                        </span>

                        <span className="flex size-4 items-center justify-center flex-none py-2.5">
                          {isSelected && (
                            <CheckIcon className="size-4 text-teal-600 dark:text-teal-400" />
                          )}
                        </span>
                      </div>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
              {hasMinRole(membership, "Admin") && (
                <>
                  <CommandSeparator />
                  <CommandGroup>
                    <CommandItem
                      value="CREATE_PROJECT"
                      className="cursor-pointer flex gap-1.5"
                      onSelect={() => {
                        navigate(href("/workspace/create-project"));
                        setQuery("");
                        setPopoverOpen(false);
                      }}
                    >
                      <div className="size-6 flex-none flex items-center justify-center border border-border rounded-full">
                        <PlusIcon className="size-4" />
                      </div>
                      Create project
                    </CommandItem>
                  </CommandGroup>
                </>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}
