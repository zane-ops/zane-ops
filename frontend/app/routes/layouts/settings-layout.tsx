import {
  ContainerIcon,
  CreditCardIcon,
  GitBranchIcon,
  KeyIcon,
  type LucideIcon,
  TerminalIcon,
  TicketCheckIcon,
  UserIcon
} from "lucide-react";
import { Link, Outlet } from "react-router";
import { NavLink } from "react-router";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/settings-layout";

export function meta() {
  return [metaTitle("Settings")] satisfies ReturnType<Route.MetaFunction>;
}

type NavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
  disabled?: boolean;
};

const sidebarNavItems: NavItem[] = [
  {
    title: "Account",
    href: "account",
    icon: UserIcon
  },
  {
    title: "SSH Keys",
    href: "ssh-keys",
    icon: KeyIcon
  },
  {
    title: "Console",
    href: "server-console",
    icon: TerminalIcon
  },
  {
    title: "Git",
    href: "git-apps",
    icon: GitBranchIcon
  },
  {
    title: "Registry Credentials",
    href: "shared-credentials",
    icon: CreditCardIcon
  },
  {
    title: "Build Registries",
    href: "build-registries",
    icon: ContainerIcon
  }
];

export default function SettingsLayoutPage({}: Route.ComponentProps) {
  return (
    <>
      <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to="/" prefetch="intent">
                Projects
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Settings</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="my-6 grid md:grid-cols-12 gap-6 md:gap-4 relative max-w-full">
        <div className="md:col-span-full">
          <h1 className="text-3xl font-medium">Settings</h1>
          <h4 className="text-sm mt-2 opacity-60">
            Manage your global settings
          </h4>
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
                      // if we don't do this, the default route "/settings" would always be active
                      end={item.href.length === 0}
                    >
                      <item.icon size={15} className="text-grey flex-none" />
                      {item.title}
                    </NavLink>
                  </Button>
                </li>
              ))}
            </ul>
          </nav>
        </aside>
        <div className="md:col-span-9 overflow-hidden py-1 px-2">
          <Outlet />
        </div>
      </div>
    </>
  );
}
