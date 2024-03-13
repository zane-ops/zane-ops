import { Link, type LinkProps } from "@tanstack/react-router";
import React from "react";

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
