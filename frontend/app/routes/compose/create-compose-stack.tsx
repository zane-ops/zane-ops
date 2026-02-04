import { ArrowRightIcon, FileTextIcon } from "lucide-react";
import { Link } from "react-router";
import { DokployLogo } from "~/components/dokploy-logo";
import { ZaneOpsLogo } from "~/components/logo";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator
} from "~/components/ui/breadcrumb";
import { Button } from "~/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from "~/components/ui/tooltip";
import { cn } from "~/lib/utils";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/create-compose-stack";

export function meta() {
  return [
    metaTitle("Create Compose Stack")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateComposeStackPage({
  params
}: Route.ComponentProps) {
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
                params.envSlug === "production"
                  ? "text-green-500 dark:text-primary"
                  : params.envSlug.startsWith("preview")
                    ? "text-link"
                    : ""
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
            <BreadcrumbPage>Create compose stack</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex h-[70vh] grow justify-center items-center">
        <div className="card  flex  md:w-[50%] lg:w-[30%] w-full flex-col gap-6">
          <h1 className="text-3xl font-bold">New Compose Stack</h1>
          <div className="flex flex-col gap-3">
            <TooltipProvider>
              <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    aria-disabled="true"
                    variant="secondary"
                    asChild
                    className="flex gap-2.5 items-center font-semibold justify-center p-10"
                  >
                    <Link to="#">
                      <ZaneOpsLogo className="flex-none size-8" />
                      <span>From ZaneOps template</span>
                      <ArrowRightIcon className="flex-none" />
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left">Coming soon ✨</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <Button
              asChild
              variant="secondary"
              className="flex gap-2.5 font-semibold items-center justify-center p-10"
            >
              <Link to="./dokploy" prefetch="intent">
                <DokployLogo className="flex-none size-8" />
                <span>From Dokploy template</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>

            <Button
              asChild
              variant="secondary"
              className="flex gap-2.5 items-center  font-semibold  justify-center p-10"
            >
              <Link to="./file" prefetch="intent">
                <FileTextIcon className="flex-none" />
                <span>From compose file contents</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
