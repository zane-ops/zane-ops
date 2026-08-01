import {
  ContainerIcon,
  FolderPlusIcon,
  KeyRoundIcon,
  LaptopMinimalIcon,
  LogOutIcon,
  type LucideIcon,
  MoonIcon,
  SunIcon,
  UserPlusIcon
} from "lucide-react";
import * as React from "react";
import { href, useFetcher } from "react-router";
import type { CommandBarActionGroup } from "~/components/commandbar/commandbar";
import {
  type Theme,
  getNextTheme,
  useThemeStore
} from "~/components/theme-store";

const THEME_ACTION: Record<Theme, { title: string; icon: LucideIcon }> = {
  LIGHT: { title: "Switch To Light Theme", icon: SunIcon },
  DARK: { title: "Switch To Dark Theme", icon: MoonIcon },
  SYSTEM: { title: "Switch To System Theme", icon: LaptopMinimalIcon }
};

/**
 * Workspace wide actions, the ones scoped to a project, a service or a
 * deployment depend on the current route and are not included here.
 */
export function useCommandBarActionGroups(): CommandBarActionGroup[] {
  const fetcher = useFetcher();
  const { theme, toggleTheme } = useThemeStore();

  return React.useMemo(
    () => [
      {
        heading: "Workspace",
        minRole: "Admin",
        items: [
          {
            id: "create-project",
            title: "New Project",
            href: href("/workspace/create-project"),
            icon: FolderPlusIcon
          },
          {
            id: "invite-member",
            title: "Invite Member",
            href: href("/workspace/settings/team/invite"),
            icon: UserPlusIcon
          }
        ]
      },

      {
        heading: "Account",
        items: [
          {
            id: "toggle-theme",
            // show where the toggle takes you, not where you are
            ...THEME_ACTION[getNextTheme(theme)],
            onSelect: toggleTheme
          },
          {
            id: "logout",
            title: "Log Out",
            icon: LogOutIcon,
            // `/logout` redirects on GET, it only accepts a POST
            onSelect: () =>
              fetcher.submit(null, { method: "post", action: href("/logout") })
          }
        ]
      },
      {
        heading: "Server Admin",
        minRole: "ServerAdmin",
        items: [
          {
            id: "create-ssh-key",
            title: "New SSH Key",
            href: href("/admin/ssh-keys/new"),
            icon: KeyRoundIcon
          },
          {
            id: "create-build-registry",
            title: "New Build Registry",
            href: href("/admin/build-registries/new"),
            icon: ContainerIcon
          }
        ]
      }
    ],
    [theme, toggleTheme, fetcher]
  );
}
