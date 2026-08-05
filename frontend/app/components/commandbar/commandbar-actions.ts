import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftRightIcon,
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
import { useCommandBarStore } from "~/components/commandbar/commandbar-store";
import type { CommandBarActionGroup } from "~/components/commandbar/commandbar-types";
import { type Theme, useThemeStore } from "~/components/theme-store";
import { userQueries } from "~/lib/queries";

const THEME_ACTIONS = [
  { theme: "LIGHT", title: "Switch To Light Theme", icon: SunIcon },
  { theme: "DARK", title: "Switch To Dark Theme", icon: MoonIcon },
  { theme: "SYSTEM", title: "Switch To System Theme", icon: LaptopMinimalIcon }
] as const satisfies readonly {
  theme: Theme;
  title: string;
  icon: LucideIcon;
}[];

/**
 * Workspace wide actions, the ones scoped to a project, a service or a
 * deployment depend on the current route and are not included here.
 */
export function useCommandBarActionGroups(): CommandBarActionGroup[] {
  const fetcher = useFetcher();
  const { theme: currentTheme, setTheme } = useThemeStore();
  const setView = useCommandBarStore((state) => state.setView);

  const { data: memberships } = useQuery(userQueries.memberships);
  // with a single workspace there is nothing to switch to
  const canSwitchWorkspace = (memberships ?? []).length > 1;

  return React.useMemo(() => {
    // the theme already in use is not worth offering
    const themeActions = THEME_ACTIONS.filter(
      (action) => action.theme !== currentTheme
    ).map(({ theme, title, icon }) => ({
      id: `switch-to-${theme.toLowerCase()}-theme`,
      title,
      icon,
      onSelect: () => setTheme(theme)
    }));

    return [
      ...(canSwitchWorkspace
        ? [
            {
              heading: "Workspaces",
              items: [
                {
                  id: "switch-workspace",
                  title: "Switch Workspace",
                  icon: ArrowLeftRightIcon,
                  // the list becomes the workspace picker, the bar stays open
                  keepOpen: true,
                  onSelect: () => setView("workspace")
                }
              ]
            } satisfies CommandBarActionGroup
          ]
        : []),
      {
        heading: "Workspace",
        minRole: "Admin",
        items: [
          {
            id: "create-project",
            title: "Create Project",
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
      },
      {
        heading: "Account",
        items: [
          ...themeActions,
          {
            id: "logout",
            title: "Log Out",
            icon: LogOutIcon,
            // `/logout` redirects on GET, it only accepts a POST
            onSelect: () =>
              fetcher.submit(null, { method: "post", action: href("/logout") })
          }
        ]
      }
    ];
  }, [currentTheme, setTheme, fetcher, canSwitchWorkspace, setView]);
}
