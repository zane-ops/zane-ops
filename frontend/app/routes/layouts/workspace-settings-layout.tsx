import {
  Building2Icon,
  CreditCardIcon,
  GitBranchIcon,
  MailIcon,
  UsersIcon
} from "lucide-react";
import { NavLink, Outlet, href } from "react-router";
import type { NavItem } from "~/components/horizontal-nav-link";
import { Button } from "~/components/ui/button";
import { cn, hasMinRole, metaTitle } from "~/lib/utils";
import { useCurrentWorkspaceMembership } from "~/lib/workspace-store";
import type { Route } from "./+types/workspace-settings-layout";

export function meta() {
  return [metaTitle("Settings")] satisfies ReturnType<Route.MetaFunction>;
}

export default function SettingsLayoutPage({}: Route.ComponentProps) {
  const membership = useCurrentWorkspaceMembership();

  const sidebarNavItems: NavItem[] = [
    {
      title: "General",
      href: href("/workspace/settings"),
      icon: Building2Icon
    }
  ];

  if (hasMinRole(membership, "Member")) {
    sidebarNavItems.push({
      title: "Team",
      href: href("/workspace/settings/team"),
      icon: UsersIcon
    });
  }
  if (hasMinRole(membership, "Admin")) {
    sidebarNavItems.push({
      title: "User Invitations",
      href: href("/workspace/settings/invitations"),
      icon: MailIcon
    });
  }

  if (hasMinRole(membership, "Admin")) {
    sidebarNavItems.push({
      title: "Git",
      href: href("/workspace/settings/git-apps"),
      icon: GitBranchIcon
    });
  }

  // members pick a shared credential when creating a service, they just can't edit them
  if (hasMinRole(membership, "Member")) {
    sidebarNavItems.push({
      title: "Shared Credentials",
      href: href("/workspace/settings/shared-credentials"),
      icon: CreditCardIcon
    });
  }

  return (
    <>
      <div className="my-6 grid md:grid-cols-12 gap-6 md:gap-4 relative max-w-full">
        <div className="md:col-span-full">
          <h1 className="text-3xl font-medium flex items-center gap-2">
            <Building2Icon className="size-8 flex-none text-grey" />
            Workspace Settings
          </h1>
          <h4 className="text-sm mt-2 opacity-60">
            Manage your workspace settings
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
                      end={item.href === href("/workspace/settings")}
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
