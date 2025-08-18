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
import { cn, isNotFoundError } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/project-layout";

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
  const project = await queryClient.ensureQueryData(
    projectQueries.single(params.projectSlug)
  );
  return { project };
}

export default function ProjectLayout({
  params,
  loaderData: { project }
}: Route.ComponentProps) {
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
            <BreadcrumbLink asChild>
              <Link
                to={href("/project/:projectSlug/:envSlug", {
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
      </Breadcrumb>
      <div className="my-6 grid md:grid-cols-12 gap-6 relative max-w-full">
        <div className="md:col-span-12">
          <h1 className="text-3xl font-medium">
            <span className="text-grey">`</span>
            {project.slug}
            <span className="text-grey">`</span> settings
          </h1>
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
