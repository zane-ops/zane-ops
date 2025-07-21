import { useQuery } from "@tanstack/react-query";
import { ChevronDownIcon, GithubIcon, GitlabIcon } from "lucide-react";

import { Link, href, useNavigate } from "react-router";
import { GithubAppCardLink } from "~/components/github-app-cards";
import { GitlabAppCardLink } from "~/components/gitlab-app.cards";
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
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { gitAppsQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/create-private-git-service";

export function meta() {
  return [
    metaTitle("New Git Service From Git provider")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const gitAppList = await queryClient.ensureQueryData(gitAppsQueries.list);

  return {
    gitAppList
  };
}

export default function CreatePrivateGitServicePage({
  params,
  loaderData
}: Route.ComponentProps) {
  const { data: gitAppList } = useQuery({
    ...gitAppsQueries.list,
    initialData: loaderData.gitAppList
  });

  const navigate = useNavigate();

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
                  ...params,
                  envSlug: "production"
                })}
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
                to={href("/project/:projectSlug/:envSlug", params)}
                prefetch="intent"
              >
                {params.envSlug}
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbLink asChild>
              <Link
                to={`/project/${params.projectSlug}/${params.envSlug}/create-service`}
                prefetch="intent"
              >
                Create service
              </Link>
            </BreadcrumbLink>
          </BreadcrumbItem>

          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>From Git provider</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div
        className={cn(
          "flex flex-col my-10 grow justify-center items-center mx-auto",
          "gap-10"
        )}
      >
        <div className="flex w-full flex-col gap-3 md:w-1/2">
          <div className="flex flex-col items-start gap-1">
            <h1 className="text-3xl font-bold">New Git Service</h1>
            <h2 className="text-grey">Select a git app</h2>
          </div>
        </div>

        <ul
          className={cn(
            "flex flex-col gap-2 w-full md:w-1/2 relative overflow-auto h-100",
            gitAppList.length === 0 ? "my-20" : "my-6"
          )}
        >
          {gitAppList.length === 0 && (
            <div
              className={cn(
                "flex flex-col gap-2 items-center rounded-lg",
                "border-border border-dashed border-1",
                "py-8 px-10"
              )}
            >
              <h2 className="text-2xl font-medium">No git app found</h2>
              <h3 className="text-lg text-grey text-center">
                start by creating one
              </h3>
              <Menubar className="border-none w-fit">
                <MenubarMenu>
                  <MenubarTrigger asChild>
                    <Button className="flex gap-2">
                      Create <ChevronDownIcon size={18} />
                    </Button>
                  </MenubarTrigger>
                  <MenubarContent
                    align="center"
                    alignOffset={0}
                    className="border min-w-0 mx-9  border-border"
                  >
                    <MenubarContentItem
                      icon={GithubIcon}
                      text="GitHub app"
                      onClick={() => {
                        navigate(href("/settings/git-apps/create-github-app"));
                      }}
                    />

                    <MenubarContentItem
                      icon={GitlabIcon}
                      text="gitlab app"
                      onClick={() => {
                        navigate(href("/settings/git-apps/create-gitlab-app"));
                      }}
                    />
                  </MenubarContent>
                </MenubarMenu>
              </Menubar>
            </div>
          )}

          {gitAppList.map((git_app) => (
            <li key={git_app.id} className="lg:w-3/4">
              {git_app.github && (
                <GithubAppCardLink
                  app={git_app.github}
                  parent_id={git_app.id}
                />
              )}
              {git_app.gitlab && (
                <GitlabAppCardLink
                  app={git_app.gitlab}
                  parent_id={git_app.id}
                />
              )}
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}
