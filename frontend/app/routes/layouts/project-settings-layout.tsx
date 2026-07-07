import {
  BookDashedIcon,
  type LucideIcon,
  NetworkIcon,
  SettingsIcon
} from "lucide-react";
import { Link, NavLink, Outlet, href } from "react-router";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import { projectQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, isNotFoundError } from "~/lib/utils";
import { metaTitle, stringToColor } from "~/utils";
import type { Route } from "./+types/project-settings-layout";

export function meta({ error, params }: Route.MetaArgs) {
  const title = !error
    ? `\`${params.projectSlug}\` settings`
    : isNotFoundError(error)
      ? "Error 404 - Project does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

type NavItem = {
  title: string;
  href: string;
  icon: LucideIcon;
  disabled?: boolean;
};

const sidebarNavItems: NavItem[] = [
  {
    title: "General",
    href: "",
    icon: SettingsIcon
  },
  {
    title: "Environments",
    href: "environments",
    icon: NetworkIcon
  },
  {
    title: "Preview Templates",
    href: "preview-templates",
    icon: BookDashedIcon
  }
];

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const project = await queryClient.ensureQueryData(
    projectQueries.single(params.workspaceId, params.projectSlug)
  );
  return { project };
}

export default function ProjectLayout({
  params,
  loaderData: { project }
}: Route.ComponentProps) {
  const projectColor = stringToColor(project.slug);
  return (
    <>
      {/* <Breadcrumb>
        <BreadcrumbList className="text-sm">
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link to={href("/:workspaceId", params)} prefetch="intent">
                Projects
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={href("/:workspaceId/project/:projectSlug/:envSlug", {
                  workspaceId: params.workspaceId,
                  projectSlug: params.projectSlug,
                  envSlug: "production"
                })}
                prefetch="intent"
              >
                {project.slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Settings</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb> */}
      <div className="mt-11.5 my-6 grid md:grid-cols-12 gap-6 relative max-w-full">
        <div className="md:col-span-12">
          <div className="flex items-center gap-4">
            <Link
              to={href("/:workspaceId/project/:projectSlug/:envSlug", {
                ...params,
                envSlug: "production"
              })}
              style={
                {
                  "--color-light": projectColor.light,
                  "--color-dark": projectColor.dark
                } as React.CSSProperties
              }
              className={cn(
                "size-12 text-xl flex-none rounded-md flex items-center justify-center",
                "text-[var(--color-light)] dark:text-[var(--color-dark)]",
                "bg-[var(--color-light)]/10 dark:bg-[var(--color-dark)]/10",
                "border  border-[var(--color-light)]/10 dark:border-[var(--color-dark)]/10",
                "focus-visible:outline-hidden focus-visible:ring-2",
                "focus-visible:ring-ring focus-visible:ring-offset-2",
                "ring-offset-background transition-colors"
              )}
            >
              <span>{project.slug.charAt(0).toUpperCase()}</span>
            </Link>
            <h1 className="text-2xl font-medium inline-flex gap-4 items-center">
              <span className="sr-only">{project.slug}</span>
              <div className="relative h-5 w-[2px] bg-grey/30 rounded-md rotate-15 flex-none" />
              <span>Project settings</span>
            </h1>
          </div>
          <h4 className="text-sm mt-2 opacity-60">
            Manage your project settings
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
