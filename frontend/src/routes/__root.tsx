import {
  Link,
  type LinkProps,
  Outlet,
  createRootRoute
} from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import * as React from "react";
import { TailwindIndicator } from "~/components/tailwind-indicator";

export const Route = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <TailwindIndicator />
      <TanStackRouterDevtools />
    </>
  )
});

export type NavLinkProps = Omit<LinkProps, "to" | "ref" | "activeProps"> & {
  href: string;
};

export const NavLink = React.forwardRef<
  React.ElementRef<typeof Link>,
  NavLinkProps
>(function NavLink({ href, ...props }, ref) {
  return (
    <Link
      ref={ref}
      {...props}
      activeProps={{
        "aria-current": "page"
      }}
      to={href}
    />
  );
});
