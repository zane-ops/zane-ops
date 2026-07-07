import { ArrowRightIcon, FileTextIcon } from "lucide-react";
import { Link, href } from "react-router";
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
      <div className="flex h-[70vh] grow justify-center items-center">
        <div className="card  flex  md:w-[50%] lg:w-[30%] w-full flex-col gap-6">
          <h1 className="text-3xl font-bold">New Compose Stack</h1>
          <div className="flex flex-col gap-3">
            <Button
              type="button"
              variant="secondary"
              asChild
              className="flex gap-2.5 items-center font-semibold justify-center p-10"
            >
              <Link to="./template">
                <ZaneOpsLogo className="flex-none size-8" />
                <span>From ZaneOps template</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>

            <Button
              asChild
              variant="secondary"
              className="flex gap-3 font-semibold items-center justify-center p-10"
            >
              <Link to="./dokploy" prefetch="intent">
                <DokployLogo className="flex-none size-8" />
                <span className="text-center">
                  From Dokploy template <br /> (experimental)
                </span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>

            <Button
              asChild
              variant="secondary"
              className="flex gap-2.5 items-center  font-semibold  justify-center p-10"
            >
              <Link to="./compose-contents" prefetch="intent">
                <FileTextIcon className="flex-none" />
                <span>From docker-compose.yml</span>
                <ArrowRightIcon className="flex-none" />
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
