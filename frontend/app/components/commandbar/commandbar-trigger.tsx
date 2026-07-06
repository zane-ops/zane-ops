import { CommandIcon, SearchIcon } from "lucide-react";
import { Button } from "~/components/ui/button";

export type CommandBarTriggerProps = {};

export function CommandBarTrigger({}: CommandBarTriggerProps) {
  return (
    <Button
      variant="outline"
      className="pl-3 pr-4 py-1 rounded-lg text-grey border-grey/20 gap-2 hidden md:inline-flex"
    >
      <SearchIcon className="size-4 flex-none" />
      <span>Search for projects, services...</span>
      &nbsp;
      <span className="font-mono px-1.5 gap-0.5 inline-flex items-center bg-muted rounded-md py-0.5 text-foreground">
        <CommandIcon className="size-4 flex-none" /> K
      </span>
    </Button>
  );
}
