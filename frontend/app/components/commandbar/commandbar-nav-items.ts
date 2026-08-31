import {
  BrushCleaningIcon,
  Building2Icon,
  ContainerIcon,
  CreditCardIcon,
  FolderIcon,
  GitBranchIcon,
  GlobeIcon,
  KeyRoundIcon,
  Link2Icon,
  LockIcon,
  MailIcon,
  ScaleIcon,
  TerminalIcon,
  UserIcon,
  UsersIcon
} from "lucide-react";
import { href } from "react-router";
import type { CommandBarNavGroup } from "~/components/commandbar/commandbar-types";
import { BUILD_EDITION } from "~/lib/constants";

export const WORKSPACE_NAV_GROUP: CommandBarNavGroup = {
  heading: "Workspace",
  minRole: "Viewer",
  items: [
    {
      id: "nav-workspace-projects",
      title: "Projects",
      href: href("/workspace"),
      icon: FolderIcon,
      minRole: "Viewer"
    },
    {
      id: "nav-workspace-settings",
      title: "Workspace Settings",
      href: href("/workspace/settings"),
      icon: Building2Icon,
      minRole: "Viewer"
    },
    {
      id: "nav-workspace-team",
      title: "Team",
      href: href("/workspace/settings/team"),
      icon: UsersIcon,
      minRole: "Member"
    },
    {
      id: "nav-workspace-user-invitations",
      title: "User Invitations",
      href: href("/workspace/settings/invitations"),
      icon: MailIcon,
      minRole: "Admin"
    },
    {
      id: "nav-workspace-git-apps",
      title: "Git Apps",
      href: href("/workspace/settings/git-apps"),
      icon: GitBranchIcon,
      minRole: "Admin"
    },
    {
      id: "nav-workspace-shared-credentials",
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
      id: "nav-account-settings",
      title: "Account Settings",
      href: href("/account"),
      icon: UserIcon
    },
    {
      id: "nav-account-change-password",
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
const SERVER_ADMIN_NAV_GROUP: CommandBarNavGroup = {
  heading: "Server Admin",
  minRole: "ServerAdmin",
  items: [
    {
      id: "nav-admin-users",
      title: "Users",
      href: href("/admin/users"),
      icon: UsersIcon
    },
    {
      id: "nav-admin-workspaces",
      title: "Workspaces",
      href: href("/admin/workspaces"),
      icon: Building2Icon
    },
    {
      id: "nav-admin-password-links",
      title: "Password Reset Links",
      href: href("/admin/password-links"),
      icon: Link2Icon
    },
    {
      id: "nav-admin-ssh-keys",
      title: "SSH Keys",
      href: href("/admin/ssh-keys"),
      icon: KeyRoundIcon
    },
    {
      id: "nav-admin-build-registries",
      title: "Build Registries",
      href: href("/admin/build-registries"),
      icon: ContainerIcon
    },
    {
      id: "nav-admin-server-console",
      title: "Server Console",
      href: href("/admin/server-console"),
      icon: TerminalIcon
    },
    {
      id: "nav-admin-automation",
      href: href("/admin/automation"),
      title: "Maintenance & Cleanup",
      icon: BrushCleaningIcon
    },
    {
      id: "nav-admin-http-logs",
      href: href("/admin/http-logs"),
      title: "Global HTTP Logs",
      icon: GlobeIcon
    }
  ]
};

if (BUILD_EDITION === "ee") {
  SERVER_ADMIN_NAV_GROUP.items.push({
    id: "nav-admin-license",
    href: href("/admin/license"),
    title: "License",
    icon: ScaleIcon
  });
}

const MAIN_NAV_GROUPS: CommandBarNavGroup[] = [
  WORKSPACE_NAV_GROUP,
  ACCOUNT_NAV_GROUP,
  SERVER_ADMIN_NAV_GROUP
];

export { MAIN_NAV_GROUPS, SERVER_ADMIN_NAV_GROUP };
