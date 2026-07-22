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
  size?: "default" | "sm";
};

export function WorkspaceRoleBadge({
  role,
  className,
  size = "default"
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
      className={cn(
        {
          "gap-1.5 [&_svg]:size-4!": size === "default",
          "gap-1 py-0 px-1.5 text-xs [&_svg]:size-3!": size === "sm"
        },
        className
      )}
    >
      <span>{role}</span>
      <Icon className={cn("flex-none")} />
    </StatusBadge>
  );
}
