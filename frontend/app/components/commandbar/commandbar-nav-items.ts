import {
  Building2Icon,
  ContainerIcon,
  CreditCardIcon,
  FolderIcon,
  GitBranchIcon,
  KeyRoundIcon,
  LockIcon,
  MailIcon,
  TerminalIcon,
  UserIcon,
  UsersIcon
} from "lucide-react";
import { href } from "react-router";
import type { CommandBarNavGroup } from "~/components/commandbar/commandbar-types";

export const WORKSPACE_NAV_GROUP: CommandBarNavGroup = {
  heading: "Workspace",
  minRole: "Viewer",
  items: [
    {
      title: "Projects",
      href: href("/workspace"),
      icon: FolderIcon,
      minRole: "Viewer"
    },
    {
      title: "Workspace Settings",
      href: href("/workspace/settings"),
      icon: Building2Icon,
      minRole: "Viewer"
    },
    {
      title: "Team",
      href: href("/workspace/settings/team"),
      icon: UsersIcon,
      minRole: "Member"
    },
    {
      title: "User Invitations",
      href: href("/workspace/settings/invitations"),
      icon: MailIcon,
      minRole: "Admin"
    },
    {
      title: "Git Apps",
      href: href("/workspace/settings/git-apps"),
      icon: GitBranchIcon,
      minRole: "Admin"
    },
    {
      // members pick a shared credential when creating a service, they just can't edit them
      title: "Shared Credentials",
      href: href("/workspace/settings/shared-credentials"),
      icon: CreditCardIcon,
      minRole: "Member"
    }
  ]
};

export const ACCOUNT_NAV_GROUP: CommandBarNavGroup = {
  heading: "Account",
  items: [
    {
      title: "Account Settings",
      href: href("/account"),
      icon: UserIcon
    },
    {
      title: "Change Password",
      href: href("/account/change-password"),
      icon: LockIcon
    }
  ]
};

/**
 * Only shown within the server admin layout (`/admin/*`), these routes live
 * outside of the workspace layout entirely.
 */
export const SERVER_ADMIN_NAV_GROUP: CommandBarNavGroup = {
  heading: "Server Admin",
  minRole: "ServerAdmin",
  items: [
    {
      title: "Users",
      href: href("/admin"),
      icon: UsersIcon
    },
    {
      title: "SSH Keys",
      href: href("/admin/ssh-keys"),
      icon: KeyRoundIcon
    },
    {
      title: "Build Registries",
      href: href("/admin/build-registries"),
      icon: ContainerIcon
    },
    {
      title: "Server Console",
      href: href("/admin/server-console"),
      icon: TerminalIcon
    }
  ]
};

export const MAIN_NAV_GROUPS: CommandBarNavGroup[] = [
  WORKSPACE_NAV_GROUP,
  ACCOUNT_NAV_GROUP,
  SERVER_ADMIN_NAV_GROUP
];
