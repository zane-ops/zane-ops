import { CommandIcon, SearchIcon } from "lucide-react";
import * as React from "react";
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import { Button } from "~/components/ui/button";
import { cn } from "~/lib/utils";

export type CommandBarTriggerProps = {
  className?: string;
};

export function CommandBarTrigger({ className }: CommandBarTriggerProps) {
  const setOpen = useCommandBarStore((s) => s.setOpen);

  const isMac = useIsMac();

  return (
    <Button
      variant="outline"
      onClick={() => setOpen(true)}
      className={cn(
        "h-8 text-sm pl-3 pr-2 py-1 rounded-lg text-grey border-grey/20 gap-2",
        "md:inline-flex hidden",
        className
      )}
    >
      <SearchIcon className="size-3 flex-none" />
      <span>Command palette</span>
      &nbsp;
      <span className="font-mono gap-0.5 inline-flex items-center bg-muted rounded-md  px-1 text-foreground">
        {isMac ? (
          <CommandIcon className="size-3 flex-none" />
        ) : (
          <>
            <span>Ctrl</span>
            <span>+</span>
          </>
        )}
        <span>K</span>
      </span>
    </Button>
  );
}

function useIsMac() {
  const [isMac, setIsMac] = React.useState(false);

  React.useEffect(() => {
    setIsMac(/Mac|iPhone|iPod|iPad/.test(navigator.platform));
  }, []);

  return isMac;
}
