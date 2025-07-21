import {
  ArrowRightIcon,
  ContainerIcon,
  GithubIcon,
  LinkIcon
} from "lucide-react";
import { Link } from "react-router";
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
import { type Route } from "./+types/create-service";

export function meta() {
  return [metaTitle("Create Service")] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateServicePage({ params }: Route.ComponentProps) {
  return (
    <div>
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
                to={`/project/${params.projectSlug}/production`}
                prefetch="intent"
              >
                {params.projectSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink
              asChild
              className={cn(
                params.envSlug !== "production"
                  ? "text-link"
                  : "text-green-500 dark:text-primary"
              )}
            >
              <Link
                to={`/project/${params.projectSlug}/${params.envSlug}`}
                prefetch="intent"
              >
                {params.envSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Create service</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex h-[70vh] grow justify-center items-center">
        <div className="card  flex  md:w-[50%] lg:w-[30%] w-full flex-col gap-6">
          <h1 className="text-3xl font-bold">New Service</h1>
          <div className="flex flex-col gap-3">
            <Button
              asChild
              variant="secondary"
              className="flex gap-2.5 items-center  font-semibold  justify-center p-10"
            >
              <Link to="./git-private" prefetch="intent">
                <GithubIcon className="flex-none" />
                <span>From Git provider</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>

            <Button
              asChild
              variant="secondary"
              className="flex gap-2.5 items-center  font-semibold  justify-center p-10"
            >
              <Link to="./git-public" prefetch="intent">
                <LinkIcon className="flex-none" />
                <span>From public Git repo URL</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>

            <Button
              asChild
              variant="secondary"
              className="flex gap-2.5  font-semibold items-center justify-center p-10"
            >
              <Link to="./docker" prefetch="intent">
                <ContainerIcon className="flex-none" />
                <span>From Docker Image</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
