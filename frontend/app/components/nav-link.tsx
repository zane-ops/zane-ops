import { type NavLinkProps, NavLink as ReactRouterNavLink } from "react-router";
import { cn } from "~/lib/utils";

export function NavLink({ className, ...props }: NavLinkProps) {
  return (
    <ReactRouterNavLink
      {...props}
      end
      prefetch="intent"
      className={cn(
        "gap-2 inline-flex items-center justify-center whitespace-nowrap px-3 py-2 text-sm font-medium transition-all focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
        "aria-[current=page]:border-b-2 aria-[current=page]:border-card-foreground aria-[current=page]:text-card-foreground",
        className
      )}
    />
  );
}
