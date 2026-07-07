import { CommandIcon, SearchIcon } from "lucide-react";
import { Button } from "~/components/ui/button";

export type CommandBarTriggerProps = {};

export function CommandBarTrigger({}: CommandBarTriggerProps) {
  return (
    <Button
      variant="outline"
      className="h-8 text-sm pl-3 pr-2 py-1 rounded-lg text-grey border-grey/20 gap-2 hidden md:inline-flex"
    >
      <SearchIcon className="size-3 flex-none" />
      <span>Command palette</span>
      &nbsp;
      <span className="font-mono gap-0.5 inline-flex items-center bg-muted rounded-md  px-1 text-foreground">
        <CommandIcon className="size-3 flex-none" /> K
      </span>
    </Button>
  );
}
