import { Link } from "react-router";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { cn, isNotFoundError } from "~/lib/utils";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/compose-stack-details";

export function meta({ params, error }: Route.MetaArgs) {
  const title = !error
    ? params.composeStackSlug
    : isNotFoundError(error)
      ? "Error 404 - Compose Stack does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export default function ComposeStackDetailsPage({
  params: {
    projectSlug: project_slug,
    composeStackSlug: stack_slug,
    envSlug: env_slug
  }
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
                to={`/project/${project_slug}/production`}
                prefetch="intent"
              >
                {project_slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              asChild
              className={cn(
                env_slug === "production"
                  ? "text-green-500 dark:text-primary"
                  : env_slug.startsWith("preview")
                    ? "text-link"
                    : ""
              )}
            >
              <Link
                to={`/project/${project_slug}/${env_slug}`}
                prefetch="intent"
              >
                {env_slug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>{stack_slug}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
    </>
  );
}
