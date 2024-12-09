import React from "react";
import { Link, type LinkProps } from "react-router";

export type NavLinkProps = Omit<LinkProps, "to" | "ref" | "activeProps"> & {
  href: string;
};

export const NavLink = function NavLink({
  ref,
  href,
  ...props
}: NavLinkProps & {
  ref?: React.RefObject<React.ComponentRef<typeof Link>>;
}) {
  return (
    <Link
      ref={ref}
      {...props}
      // activeProps={{
      //   "aria-current": "page"
      // }}
      to={href}
    />
  );
};
