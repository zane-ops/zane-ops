import * as React from "react";

import { cn } from "~/lib/utils";

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "flex h-10 w-full placeholder:text-gray-400  rounded-md border border-input bg-background px-3 py-5 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        "[&[type='datetime-local']]:py-2",
        className
      )}
      {...props}
    />
  );
}
