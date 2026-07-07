import * as React from "react";
import { Link, href } from "react-router";
import { ThemedLogo } from "~/components/logo";

import { cn } from "~/lib/utils";

type HeaderProps = {
  leftSlot?: React.ReactNode;
  rigthSlot?: React.ReactNode;
};

export function Header({ leftSlot, rigthSlot }: HeaderProps) {
  return (
    <>
      {!import.meta.env.PROD && (
        <div
          className={cn(
            "py-0.5 bg-red-500 text-white text-center fixed top-0 left-0 right-0  z-49",
            "w-full"
          )}
        >
          <p>⚠️ YOU ARE IN DEV ⚠️</p>
        </div>
      )}

      <header
        className={cn(
          "flex px-6 py-4 items-center gap-4",
          "border-b border-opacity-65 border-border bg-toggle justify-between sticky top-0 z-60",
          !import.meta.env.PROD && "top-7"
        )}
      >
        <Link
          to={href("/")}
          className={cn(
            "focus-visible:outline-hidden focus-visible:ring-2",
            "focus-visible:ring-ring focus-visible:ring-offset-2",
            "ring-offset-background transition-colors",
            "rounded-md"
          )}
        >
          <ThemedLogo className="flex-none size-10 mr-3" />
        </Link>

        {React.Children.toArray(leftSlot)
          .filter(Boolean)
          .map((child, idx) => (
            <React.Fragment key={idx}>
              <div className="relative top-0.5 h-5 w-[2px] bg-grey/30 rounded-md rotate-15 flex-none" />
              {child}
            </React.Fragment>
          ))}

        <div className="flex grow  w-full items-center" />

        {rigthSlot}
      </header>
    </>
  );
}
