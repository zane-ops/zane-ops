import { useQuery } from "@tanstack/react-query";
import { GithubIcon, LockIcon } from "lucide-react";
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

type GithubRepositoryListInputProps = {
  githubAppId: string;
  selectedRepository: GitRepository | null;
  onSelect: (repository: GitRepository) => void;
  hasError?: boolean;
  disabled?: boolean;
  className?: string;
};

export function GithubRepositoryListInput({
  githubAppId,
  onSelect,
  hasError,
  selectedRepository,
  disabled,
  className
}: GithubRepositoryListInputProps) {
  const [isComboxOpen, setComboxOpen] = React.useState(false);
  const [repoSearchQuery, setRepoSearchQuery] = React.useState(
    selectedRepository
      ? `${selectedRepository.owner}/${selectedRepository.repo}`
      : ""
  );
  const [debouncedValue] = useDebounce(repoSearchQuery, 150);

  const repositoriesListQuery = useQuery(
    gitAppsQueries.githubRepositories(githubAppId, {
      query: debouncedValue
    })
  );

  const repositories = repositoriesListQuery.data ?? [];
  const repositoriesToShow = [...repositories];
  if (repositoriesToShow.length === 0 && selectedRepository !== null) {
    repositoriesToShow.push(selectedRepository);
  }

  return (
    <Command shouldFilter={false} label="Image">
      <CommandInput
        id="image"
        onFocus={() => setComboxOpen(true)}
        onValueChange={(query) => {
          setRepoSearchQuery(query);
          setComboxOpen(true);
        }}
        disabled={disabled}
        onBlur={() => {
          setRepoSearchQuery(
            selectedRepository
              ? `${selectedRepository.owner}/${selectedRepository.repo}`
              : ""
          );
          setComboxOpen(false);
        }}
        className={cn("p-3", className)}
        aria-hidden="true"
        value={repoSearchQuery}
        placeholder="ex: zane-ops/zane-ops"
        name="image"
        aria-invalid={hasError}
      />
      <CommandList
        className={cn({
          "hidden!": !isComboxOpen
        })}
      >
        {repositoriesToShow.map((repo) => {
          const fullPath = `${repo.owner}/${repo.repo}`;
          return (
            <CommandItem
              key={repo.id}
              value={fullPath}
              className="flex items-start gap-2"
              onSelect={(value) => {
                onSelect(repo);
                setRepoSearchQuery(value);
                setComboxOpen(false);
              }}
            >
              <GithubIcon size={15} className="flex-none relative top-1" />
              <div className="flex items-center gap-1">
                <span>{fullPath}</span>
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
