import {
  CrownIcon,
  type LucideIcon,
  ShieldIcon,
  UserIcon,
  UserSearchIcon
} from "lucide-react";
import type { WorkspaceRoleName } from "~/api/types";
import { StatusBadge } from "~/components/status-badge";
import { cn } from "~/lib/utils";

export type WorkspaceRoleBadgeProps = {
  role: WorkspaceRoleName;
  className?: string;
};

export function WorkspaceRoleBadge({
  role,
  className
}: WorkspaceRoleBadgeProps) {
  let Icon: LucideIcon;
  switch (role) {
    case "Member":
      Icon = UserIcon;
      break;
    case "Admin":
      Icon = ShieldIcon;
      break;
    case "Owner":
      Icon = CrownIcon;
      break;
    default:
      Icon = UserSearchIcon;
      break;
  }
  return (
    <StatusBadge
      color="gray"
      pingState="hidden"
      className={cn("gap-1.5", className)}
    >
      <span>{role}</span>
      <Icon className="size-4 flex-none" />
    </StatusBadge>
  );
}
