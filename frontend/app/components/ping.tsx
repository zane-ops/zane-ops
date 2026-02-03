import type { StatusBadgeColor } from "~/components/status-badge";
import { cn } from "~/lib/utils";

export type PingProps = {
  className?: string;
  color?: StatusBadgeColor;
  state?: "animated" | "static";
};
export function Ping({
  className,
  color = "green",
  state = "animated"
}: PingProps) {
  return (
    <span className={cn("relative inline-flex h-2 w-2", className)}>
      {state === "animated" && (
        <span
          className={cn(
            "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
            {
              "bg-green-500": color === "green",
              "bg-red-500": color === "red",
              "bg-yellow-500": color === "yellow",
              "bg-gray-500": color === "gray",
              "bg-blue-500": color === "blue"
            }
          )}
        />
      )}

      <span
        className={cn("relative inline-flex rounded-full h-2 w-2 ", {
          "bg-green-500": color === "green",
          "bg-red-500": color === "red",
          "bg-yellow-500": color === "yellow",
          "bg-gray-500": color === "gray",
          "bg-blue-500": color === "blue"
        })}
      ></span>
    </span>
  );
}
