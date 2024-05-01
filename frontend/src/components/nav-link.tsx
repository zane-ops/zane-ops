import { Link } from "@tanstack/react-router";
import { forwardRef } from "react";

import type { LinkProps } from "@tanstack/react-router";
import type { ElementRef } from "react";

export type NavLinkProps = Omit<LinkProps, "to" | "ref" | "activeProps"> & {
  href: string;
};

export const NavLink = forwardRef<ElementRef<typeof Link>, NavLinkProps>(
  ({ href, ...props }, ref) => (
    <Link
      ref={ref}
      {...props}
      activeProps={{
        "aria-current": "page"
      }}
      to={href}
    />
  )
);
