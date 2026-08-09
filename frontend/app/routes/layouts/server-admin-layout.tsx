import { useQuery } from "@tanstack/react-query";
import {
  Building2Icon,
  CalendarSyncIcon,
  ContainerIcon,
  GlobeIcon,
  KeyRoundIcon,
  Link2Icon,
  ScaleIcon,
  ServerIcon,
  TerminalIcon,
  UsersIcon
} from "lucide-react";
import { NavLink, Outlet, href } from "react-router";
import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import { Header } from "~/components/header/header";
import { UserHeaderDropdown } from "~/components/header/user-header-dropdown";
import type { NavItem } from "~/components/horizontal-nav-link";
import { Button } from "~/components/ui/button";
import { BUILD_EDITION } from "~/lib/constants";
import { syncLicenseStore } from "~/lib/license-store";
import { createDevLogger } from "~/lib/logger";
import { ensureMinRole, licenseQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, metaTitle } from "~/lib/utils";
import type { Route } from "./+types/server-admin-layout";

export function meta() {
  return [metaTitle("Server Admin")] satisfies ReturnType<Route.MetaFunction>;
}

const logger = createDevLogger(import.meta.url);

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  await ensureMinRole(queryClient, "ServerAdmin");

  if (BUILD_EDITION === "ee") {
    const license = await queryClient.ensureQueryData(licenseQueries.get);
    syncLicenseStore(license);
  }
}

export default function ServerAdminLayout({
  matches: {
    "1": {
      loaderData: { user: authedUser }
    }
  }
}: Route.ComponentProps) {
  const { data: user } = useQuery({
    ...userQueries.authedUser,
    initialData: authedUser
  });

  if (!user) return null;

  return (
    <>
      <Header
        rigthSlot={[<CommandBarTrigger />, <UserHeaderDropdown user={user} />]}
      />
      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
          "flex flex-col gap-10",
          !import.meta.env.PROD ? "my-14" : "my-7"
        )}
      >
        <SettingsLayout>
          <Outlet />
        </SettingsLayout>
      </main>
    </>
  );
}

type SettingsLayoutProps = {
  children: React.ReactNode;
};

function SettingsLayout({ children }: SettingsLayoutProps) {
  const sidebarNavItems: NavItem[] = [
    {
      title: "Users",
      href: href("/admin/users"),
      icon: UsersIcon
    },
    {
      title: "Password Reset Links",
      href: href("/admin/password-links"),
      icon: Link2Icon
    },
    {
      title: "Workspaces",
      href: href("/admin/workspaces"),
      icon: Building2Icon
    },
    {
      title: "SSH Keys",
      href: href("/admin/ssh-keys"),
      icon: KeyRoundIcon
    },
    {
      title: "Console",
      href: href("/admin/server-console"),
      icon: TerminalIcon
    },
    {
      title: "Build Registries",
      href: href("/admin/build-registries"),
      icon: ContainerIcon
    }
  ];

  sidebarNavItems.push(
    {
      href: "/admin/automation",
      title: "Jobs & Schedules",
      icon: CalendarSyncIcon
    },
    {
      href: "/admin/http-logs",
      title: "Global HTTP Logs",
      icon: GlobeIcon
    }
  );

  if (BUILD_EDITION === "ee") {
    sidebarNavItems.push({
      href: href("/admin/license"),
      title: "License",
      icon: ScaleIcon
    });
  }

  return (
    <div className="grid md:grid-cols-12 gap-6 md:gap-4 relative max-w-full">
      <div className="md:col-span-full">
        <h1 className="text-3xl font-medium flex items-center gap-2">
          <ServerIcon className="size-8 flex-none text-grey" />
          <span>Server Admin</span>
        </h1>
        <h4 className="text-sm mt-2 opacity-60">Manage your server settings</h4>
      </div>
      <aside className="md:col-span-3">
        <nav className="w-full sticky top-24">
          <ul className="w-full">
            {sidebarNavItems.map((item, index) => (
              <li key={`${item.href}-${index}`} className="w-full">
                <Button size="sm" variant="ghost" asChild>
                  <NavLink
                    to={item.href}
                    prefetch="viewport"
                    className={cn(
                      "w-full text-start justify-start gap-2 aria-[current=page]:bg-muted",
                      "aria-disabled:opacity-60 aria-disabled:pointer-events-none"
                    )}
                    aria-disabled={item.disabled}
                    end={item.href === href("/admin")}
                  >
                    <item.icon size={15} className="text-grey flex-none" />
                    <span className="whitespace-break-spaces">
                      {item.title}
                    </span>
                  </NavLink>
                </Button>
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      <div className="md:col-span-9 overflow-hidden py-1 px-2">{children}</div>
    </div>
  );
}
