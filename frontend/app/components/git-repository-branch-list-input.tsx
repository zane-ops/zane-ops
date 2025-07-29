import { useQuery } from "@tanstack/react-query";
import { GitBranchIcon } from "lucide-react";
import * as React from "react";
import {
  Command,
  CommandInput,
  CommandItem,
  CommandList
} from "~/components/ui/command";
import { gitAppsQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type GitRepositoryBranchListInputProps = {
  appId?: string;
  repositoryURL: string;
  selectedBranch?: string;
  onSelect: (branch: string) => void;
  hasError?: boolean;
  disabled?: boolean;
  className?: string;
  edited?: boolean;
  searchQuery: string;
  setSearchQuery: (value: string) => void;
};

export function GitRepositoryBranchListInput({
  appId,
  onSelect,
  hasError,
  repositoryURL,
  selectedBranch,
  disabled,
  className,
  edited,
  searchQuery: branchQuery,
  setSearchQuery: setBranchQuery
}: GitRepositoryBranchListInputProps) {
  const [isComboxOpen, setComboxOpen] = React.useState(false);

  const branchesListQuery = useQuery(
    gitAppsQueries.repositoryBranches(repositoryURL, appId)
  );

  const branches = branchesListQuery.data ?? [];
  const branchesToShow = [...branches];

  if (branchesToShow.length === 0 && selectedBranch) {
    branchesToShow.push(selectedBranch);
  }

  return (
    <Command>
      <CommandInput
        id="branches-list"
        onFocus={() => setComboxOpen(true)}
        onValueChange={(query) => {
          setBranchQuery(query);
          setComboxOpen(true);
        }}
        disabled={disabled}
        onBlur={() => {
          setBranchQuery(selectedBranch ?? "");
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
        value={branchQuery}
        placeholder="ex: main"
        name="branch_name"
        aria-invalid={hasError ? "true" : undefined}
        data-edited={edited ? "true" : undefined}
      />
      <CommandList
        className={cn({
          "hidden!": !isComboxOpen
        })}
      >
        {branchesToShow.map((branch) => {
          return (
            <CommandItem
              key={branch}
              value={branch}
              className="flex items-start gap-2"
              onSelect={(value) => {
                onSelect(branch);
                setBranchQuery(value);
                setComboxOpen(false);
              }}
            >
              <div className="flex items-center gap-1">
                <GitBranchIcon size={15} className="flex-none relative top-1" />
                <span>{branch}</span>
              </div>
            </CommandItem>
          );
        })}
      </CommandList>
    </Command>
  );
}
