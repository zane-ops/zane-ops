import React, { type ReactNode } from "react";
import { cn } from "~/lib/utils";

type TrackerColor = "red" | "green" | "yellow";

interface StatusBadgeProps {
  color: TrackerColor;
  children: ReactNode;
}

export function StatusBadge({ color, children }: StatusBadgeProps) {
  let borderColor = "";
  let bgColor = "";
  let textColor = "";
  let roundedColor = "";

  switch (color) {
    case "red":
      borderColor = "border-red-600";
      bgColor = "bg-red-600 bg-opacity-10";
      textColor = "text-status-error";
      roundedColor = "bg-red-600";
      break;
    case "green":
      borderColor = "border-green-600";
      bgColor = "bg-green-600 bg-opacity-10";
      textColor = "text-status-success";
      roundedColor = "bg-green-600 ";
      break;
    case "yellow":
      borderColor = "border-yellow-600";
      bgColor = "bg-yellow-600 bg-opacity-10";
      textColor = "text-status-warning";
      roundedColor = "bg-yellow-600";
      break;
    default:
      break;
  }

  return (
    <div
      className={cn(
        "flex border md:w-fit w-40 px-3 py-1 border-opacity-60 rounded-full text-sm items-center gap-2",
        borderColor,
        bgColor,
        textColor
      )}
    >
      <div
        className={cn(
          "border w-2 h-2 text-white border-transparent p-0.5 rounded-full",
          roundedColor
        )}
      ></div>
      {children}
    </div>
  );
}
