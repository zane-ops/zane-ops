import {
  ArrowRightIcon,
  ContainerIcon,
  GithubIcon,
  LinkIcon
} from "lucide-react";
import { Link } from "react-router";
import { Button } from "~/components/ui/button";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/create-service";

export function meta() {
  return [metaTitle("Create Service")] satisfies ReturnType<Route.MetaFunction>;
}

export default function CreateServicePage({}: Route.ComponentProps) {
  return (
    <div>
      <div className="mt-5 flex h-[70vh] grow justify-center items-center">
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
