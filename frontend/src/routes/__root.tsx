import {
  createRootRoute,
  Link,
  Outlet,
  LinkProps
} from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import * as React from "react";

export const Route = createRootRoute({
  component: () => (
    <>
      <div className="p-2 flex gap-2">
        <NavLink href="/" className={`aria-[current="page"]:font-bold`}>
          home
        </NavLink>
        <NavLink href="/login" className={`aria-[current="page"]:text-red-500`}>
          welcome
        </NavLink>
      </div>
      <hr />
      <Outlet />
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

/**
 * 
 * function NavLink({ href, name }: { href: string; name: string }) {
  return (
    <>
      <Link
        activeProps={{
          style: {
            fontWeight: "bold"
          }
        }}
        to={href}
      >
        {name}
      </Link>
    </>
  );
}
 */
