import type * as React from "react";
import { useSearchParams } from "react-router";
import { httpLogSearchSchema } from "~/lib/queries";
import { cn } from "~/lib/utils";

export type HttpLogsLayoutProps = {
  children: React.ReactNode;
};

/**
 * Wraps the HTTP logs page content, it handles the maximized state and
 * provides the `#log-content` scroll root that the table observers rely on.
 */
export function HttpLogsLayout({ children }: HttpLogsLayoutProps) {
  const [searchParams] = useSearchParams();
  const search = httpLogSearchSchema.parse(searchParams);

  return (
    <div
      className={cn(
        search.isMaximized &&
          "fixed inset-0 top-28 bg-background z-50 p-5 w-full",
        search.isMaximized && !import.meta.env.DEV && "top-20"
      )}
    >
      <div
        className={cn(
          "flex flex-col gap-4 relative",
          search.isMaximized ? "container px-0 h-[82dvh]" : "h-[60dvh] mt-8"
        )}
        id="log-content"
      >
        {children}
      </div>
    </div>
  );
}
