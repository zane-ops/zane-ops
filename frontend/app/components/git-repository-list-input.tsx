import { useQuery } from "@tanstack/react-query";
import { GithubIcon, GitlabIcon, LockIcon } from "lucide-react";
import React from "react";
import { useDebounce } from "use-debounce";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import { type GitRepository, gitAppsQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";

type GitRepositoryListInputProps = {
  appId: string;
  selectedRepository: GitRepository | null;
  onSelect: (repository: GitRepository) => void;
  hasError?: boolean;
  disabled?: boolean;
  className?: string;
  edited?: boolean;
  type: "github" | "gitlab";
  repoSearchQuery: string;
  setRepoSearchQuery: (value: string) => void;
};

export function GitRepositoryListInput({
  appId,
  onSelect,
  hasError,
  selectedRepository,
  disabled,
  className,
  edited,
  type,
  repoSearchQuery,
  setRepoSearchQuery
}: GitRepositoryListInputProps) {
  const [isComboxOpen, setComboxOpen] = React.useState(false);
  const [debouncedValue] = useDebounce(repoSearchQuery, 150);

  const repositoriesListQuery = useQuery(
    gitAppsQueries.repositories(appId, {
      query: debouncedValue
    })
  );

  const repositories = repositoriesListQuery.data ?? [];
  const repositoriesToShow = [...repositories];
  if (repositoriesToShow.length === 0 && selectedRepository !== null) {
    repositoriesToShow.push(selectedRepository);
  }

  return (
    <Command shouldFilter={false}>
      <CommandInput
        id="repository-list"
        onFocus={() => setComboxOpen(true)}
        onValueChange={(query) => {
          setRepoSearchQuery(query);
          setComboxOpen(true);
        }}
        disabled={disabled}
        onBlur={() => {
          setRepoSearchQuery(selectedRepository?.path ?? "");
          setComboxOpen(false);
        }}
        className={cn(
          "p-3",
          "disabled:placeholder-shown:font-mono disabled:bg-muted data-[edited]:disabled:bg-secondary/60",
          "data-[edited]:dark:disabled:bg-secondary-foreground",
          "disabled:border-transparent disabled:opacity-100",
          "text-card-foreground",
          className
        )}
        aria-hidden="true"
        value={repoSearchQuery}
        placeholder="ex: zane-ops/zane-ops"
        name="image"
        aria-invalid={hasError ? "true" : undefined}
        data-edited={edited ? "true" : undefined}
      />
      <CommandList
        className={cn({
          "hidden!": !isComboxOpen
        })}
      >
        {repositoriesToShow.map((repo) => {
          return (
            <CommandItem
              key={repo.id}
              value={repo.path}
              className="flex items-start gap-2"
              onSelect={(value) => {
                onSelect(repo);
                setRepoSearchQuery(value);
                setComboxOpen(false);
              }}
            >
              {type === "github" ? (
                <GithubIcon size={15} className="flex-none relative top-1" />
              ) : (
                <GitlabIcon size={15} className="flex-none relative top-1" />
              )}
              <div className="flex items-center gap-1">
                <span>{repo.path}</span>
                {repo.private && (
                  <LockIcon
                    size={15}
                    className="flex-none relative text-grey"
                  />
                )}
              </div>
            </CommandItem>
          );
        })}
      </CommandList>
    </Command>
  );
}
