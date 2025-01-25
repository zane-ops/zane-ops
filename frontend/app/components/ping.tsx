import { cn } from "~/lib/utils";

export type PingProps = {
  className?: string;
};
export function Ping({ className }: PingProps) {
  return (
    <span className={cn("relative inline-flex h-2 w-2", className)}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-500 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
    </span>
  );
}
