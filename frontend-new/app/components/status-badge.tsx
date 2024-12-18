import * as React from "react";
import { cn } from "~/lib/utils";

export type StatusBadgeColor = "red" | "green" | "yellow" | "gray" | "blue";

interface StatusBadgeProps {
  color: StatusBadgeColor;
  children: React.ReactNode;
  pingState?: "animated" | "static" | "hidden";
  className?: string;
}

export function StatusBadge({
  color,
  children,
  className,
  pingState = "animated"
}: StatusBadgeProps) {
  return (
    <div
      className={cn(
        "inline-flex border w-fit whitespace-nowrap px-3 py-1 border-opacity-60 rounded-full text-sm items-center gap-2",
        {
          "bg-green-600/10 text-status-success border-green-600":
            color === "green",
          "border-red-600 bg-red-600/10 text-status-error": color === "red",
          "border-yellow-600 bg-yellow-600/10 text-status-warning":
            color === "yellow",
          "border-gray-600 bg-gray-600/10 text-status-warning":
            color === "gray",
          "border-blue-600 bg-blue-600/10 text-blue-100": color === "blue"
        },
        className
      )}
    >
      {(pingState === "animated" || pingState === "static") && (
        <div className="relative w-2 h-2">
          <span
            className={cn(
              "absolute inline-flex h-full w-full rounded-full opacity-75",
              {
                "bg-green-600 ": color === "green",
                "bg-red-600": color === "red",
                "bg-yellow-600": color === "yellow",
                "bg-gray-600": color === "gray",
                "bg-blue-600": color === "blue",
                "animate-ping": pingState === "animated"
              }
            )}
          ></span>

          <div
            className={cn(
              "relative border w-full h-full text-white border-transparent p-0.5 rounded-full",
              {
                "bg-green-600": color === "green",
                "bg-red-600": color === "red",
                "bg-yellow-600": color === "yellow",
                "bg-gray-600": color === "gray",
                "bg-blue-600": color === "blue"
              }
            )}
          ></div>
        </div>
      )}

      {children}
    </div>
  );
}
