import { useQuery } from "@tanstack/react-query";
import {
  ChevronRight,
  CommandIcon,
  ContainerIcon,
  FolderIcon,
  GithubIcon,
  GitlabIcon,
  NetworkIcon,
  Search
} from "lucide-react";
import * as React from "react";
import { href, useNavigate } from "react-router";
import { useDebounce } from "use-debounce";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import { resourceQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type CommandMenuSearchbarProps = {
  onSelect?: () => void;
};

export function CommandMenuSearchbar({ onSelect }: CommandMenuSearchbarProps) {
  const [open, setOpen] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [resourceSearchQuery, setResourceSearchQuery] = React.useState("");
  const [debouncedValue] = useDebounce(resourceSearchQuery, 300);
  const navigate = useNavigate();

  const {
    data: resourceListData,
    isLoading,
    isFetching
  } = useQuery(resourceQueries.search(debouncedValue));

  React.useEffect(() => {
    const handleEvent = (e: KeyboardEvent | MouseEvent) => {
      if (
        e instanceof KeyboardEvent &&
        e.key === "k" &&
        (e.metaKey || e.ctrlKey)
      ) {
        e.preventDefault();
        setOpen((prev) => {
          const newState = !prev;
          if (newState) {
            inputRef.current?.focus();
          } else {
            inputRef.current?.blur();
          }
          return newState;
        });
      }

      if (
        e instanceof MouseEvent &&
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        inputRef.current?.blur();
      }
    };

    document.addEventListener("keydown", handleEvent);
    document.addEventListener("mousedown", handleEvent);

    return () => {
      document.removeEventListener("keydown", handleEvent);
      document.removeEventListener("mousedown", handleEvent);
    };
  }, []);

  const resourceList = resourceListData?.data ?? [];
  const hideResultList =
    debouncedValue.trim().length === 0 || !open || isLoading || isFetching;

  return (
    <div ref={containerRef} className="relative w-full">
      <Command label="resources" shouldFilter={false}>
        <div className="relative w-full flex items-center">
          <Search size={15} className="absolute left-4 text-gray-400" />
          <CommandInput
            ref={inputRef}
            className="w-full pl-12 pr-12 m-0 text-sm rounded-md border"
            placeholder="Search for Service, Worker, CRON, etc..."
            name="resourceSearchQuery"
            value={resourceSearchQuery}
            onFocus={() => setOpen(true)}
            onValueChange={(value) => {
              setResourceSearchQuery(value);
              setOpen(true);
            }}
            // onBlur={() => setOpen(false)}
          />
          <div className="hidden md:flex absolute bg-grey/20 right-4 px-2 py-1 rounded-md items-center space-x-1">
            <CommandIcon size={15} />
            <span className="text-xs">K</span>
          </div>
        </div>

        <CommandList
          className={cn(
            "absolute -top-1 left-0 w-full shadow-lg  rounded-md max-h-[328px]",
            {
              hidden: hideResultList
            }
          )}
        >
          <CommandGroup
            heading={
              resourceList.length > 0 && (
                <span>Resources ({resourceList.length})</span>
              )
            }
          >
            <CommandEmpty>No results found.</CommandEmpty>
            {resourceList.map((resource) => (
              <CommandItem
                onSelect={() => {
                  const targetUrl =
                    resource.type === "project"
                      ? href("/project/:projectSlug/:envSlug", {
                          projectSlug: resource.slug,
                          envSlug: "production"
                        })
                      : resource.type === "environment"
                        ? href("/project/:projectSlug/:envSlug", {
                            projectSlug: resource.project_slug,
                            envSlug: resource.name
                          })
                        : href(
                            "/project/:projectSlug/:envSlug/services/:serviceSlug",
                            {
                              projectSlug: resource.project_slug,
                              envSlug: resource.environment,
                              serviceSlug: resource.slug
                            }
                          );
                  navigate(targetUrl);
                  setOpen(false);
                  onSelect?.();
                }}
                key={resource.id}
                className="block"
              >
                <div className="flex items-center gap-1 mb-1 w-full">
                  {resource.type === "project" && (
                    <FolderIcon size={15} className="flex-none" />
                  )}
                  {resource.type === "service" &&
                    (resource.kind === "DOCKER_REGISTRY" ? (
                      <ContainerIcon size={15} className="flex-none" />
                    ) : resource.git_provider === "gitlab" ? (
                      <GitlabIcon size={15} className="flex-none" />
                    ) : (
                      <GithubIcon size={15} className="flex-none" />
                    ))}
                  {resource.type === "environment" && (
                    <NetworkIcon size={15} className="flex-none" />
                  )}
                  <p>
                    {resource.type === "environment"
                      ? resource.name
                      : resource.slug}
                  </p>
                </div>
                <div className="text-link text-xs w-full">
                  {resource.type === "project" ? (
                    "projects"
                  ) : resource.type === "service" ? (
                    <div className="flex gap-0.5 items-center">
                      <span className="flex-none">projects</span>
                      <ChevronRight size={13} />
                      <span>{resource.project_slug}</span>
                      <ChevronRight className="flex-none" size={13} />
                      <div
                        className={cn(
                          "rounded-md text-link inline-flex gap-1 items-center",
                          resource.environment === "production" &&
                            "px-1.5 border-none bg-primary text-black",
                          resource.environment.startsWith("preview") &&
                            "px-2 border-none bg-secondary text-black"
                        )}
                      >
                        <span className="inline-block text-ellipsis whitespace-nowrap">
                          {resource.environment}
                        </span>
                      </div>
                      <ChevronRight className="flex-none" size={13} />
                      <span className="flex-none">services</span>
                    </div>
                  ) : (
                    <div className="flex gap-0.5 items-center">
                      <span className="flex-none">projects</span>
                      <ChevronRight size={13} />
                      <span>{resource.project_slug}</span>
                      <ChevronRight className="flex-none" size={13} />
                      <div
                        className={cn(
                          "rounded-md text-link inline-flex gap-1 items-center"
                        )}
                      >
                        <span>environments</span>
                      </div>
                    </div>
                  )}
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </Command>
    </div>
  );
}
