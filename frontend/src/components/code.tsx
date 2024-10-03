import { cn } from "~/lib/utils";

export type CodeProps = React.HTMLAttributes<HTMLDivElement>;

export function Code({ className, ...props }: CodeProps) {
  return (
    <code
      className={cn(
        "font-mono rounded-md bg-gray-400/40 dark:bg-gray-500/60 px-1 py-0.5 text-card-foreground",
        className
      )}
      {...props}
    />
  );
}
