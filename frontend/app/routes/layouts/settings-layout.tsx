import {
  Bot,
  KeyIcon,
  type LucideIcon,
  ServerIcon,
  TerminalIcon,
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
    href: "",
    icon: UserIcon
  },
  {
    title: "SSH Keys",
    href: "ssh-keys",
    icon: KeyIcon
  },
  {
    title: "Server",
    href: "server/terminal",
    icon: ServerIcon
  },
  {
    title: "Automations",
    href: "automations",
    icon: Bot,
    disabled: true
  }
  // more...
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
      <div className="my-6 grid md:grid-cols-12 gap-x-6 gap-y-8 relative max-w-full">
        <div className="md:col-span-12">
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
                      <item.icon size={15} className="text-grey" />
                      {item.title}
                    </NavLink>
                  </Button>
                </li>
              ))}
            </ul>
          </nav>
        </aside>
        <div className="md:col-span-9">
          <Outlet />
        </div>
      </div>
    </>
  );
}
