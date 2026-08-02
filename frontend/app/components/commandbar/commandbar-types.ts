import type { LucideIcon } from "lucide-react";
import type { SearchResource, UserRole } from "~/api/types";

export type CommandBarNavGroup = {
  heading: string;
  items: CommandBarNavItem[];
  minRole?: UserRole;
};

export type CommandBarNavItem = {
  href: string;
  title: string;
  icon: LucideIcon;
  showInEE?: boolean;
  minRole?: UserRole;
};

export type CommandBarSearchItem = Omit<
  CommandBarNavItem,
  "showInEE" | "minRole"
> & {
  resource: SearchResource;
  /** ancestors of the resource, ex: `["my-project", "production"]` for a service */
  parents: string[];
};

export type CommandBarSearchGroup = {
  heading: string;
  items: CommandBarSearchItem[];
};

export type CommandBarAction = {
  id: string;
  title: string;
  icon: LucideIcon;
  /** where to navigate to, runs after `onSelect` when both are set */
  href?: string;
  onSelect?: () => void;
  minRole?: UserRole;
};

export type CommandBarActionGroup = {
  heading: string;
  items: CommandBarAction[];
  minRole?: UserRole;
};
