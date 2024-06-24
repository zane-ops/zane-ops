import type { ReactNode } from "react";
import { cn } from "~/lib/utils";

type TrackerColor = "red" | "green" | "yellow";

interface StatusBadgeProps {
  color: TrackerColor;
  children: ReactNode;
}

export function StatusBadge({ color, children }: StatusBadgeProps) {
  return (
    <div
      className={cn(
        "flex border md:w-fit w-40 px-3 py-1 border-opacity-60 rounded-full text-sm items-center gap-2",
        {
          "bg-green-600 bg-opacity-10 text-status-success border-green-600":
            color === "green",
          "border-red-600 bg-red-600 bg-opacity-10 text-status-error":
            color === "red",
          "border-yellow-600 bg-yellow-600 bg-opacity-10 text-status-warning":
            color === "yellow"
        }
      )}
    >
      <div className="relative w-2 h-2">
        <span
          className={cn(
            "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
            {
              "bg-green-600 ": color === "green",
              "bg-red-600": color === "red",
              "bg-yellow-600": color === "yellow"
            }
          )}
        ></span>
        <div
          className={cn(
            "relative border w-full h-full text-white border-transparent p-0.5 rounded-full",
            {
              "bg-green-600 ": color === "green",
              "bg-red-600": color === "red",
              "bg-yellow-600": color === "yellow"
            }
          )}
        ></div>
      </div>
      {children}
    </div>
  );
}
