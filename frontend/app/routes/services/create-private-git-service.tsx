import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  ChevronDownIcon,
  GithubIcon,
  GitlabIcon
} from "lucide-react";

import { Link, href, useNavigate } from "react-router";
import { GithubAppCardLink } from "~/components/github-app-cards";
import { GitlabAppCardLink } from "~/components/gitlab-app.cards";
import { Button } from "~/components/ui/button";
import {
  Menubar,
  MenubarContent,
  MenubarContentItem,
  MenubarMenu,
  MenubarTrigger
} from "~/components/ui/menubar";
import { gitAppsQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, metaTitle } from "~/lib/utils";
import {
  getCurrentWorkspace,
  useCurrentWorkspace
} from "~/lib/workspace-store";
import type { Route } from "./+types/create-private-git-service";

export function meta() {
  return [
    metaTitle("New Git Service From Git provider")
  ] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const { id: workspaceId } = await getCurrentWorkspace(queryClient);
  const gitAppList = await queryClient.ensureQueryData(
    gitAppsQueries.list(workspaceId)
  );

  return {
    gitAppList
  };
}

export default function CreatePrivateGitServicePage({
  params,
  loaderData
}: Route.ComponentProps) {
  const workspaceId = useCurrentWorkspace().id;
  const { data: gitAppList } = useQuery({
    ...gitAppsQueries.list(workspaceId),
    initialData: loaderData.gitAppList
  });

  const navigate = useNavigate();

  return (
    <div
      className={cn(
        "flex flex-col my-10 grow justify-center items-center mx-auto",
        "gap-6"
      )}
    >
      <div className="flex w-full flex-col gap-1 md:w-1/2">
        <Link
          to={href("/project/:projectSlug/:envSlug/create-service", params)}
          className={cn(
            "text-sm text-grey",
            "flex items-center gap-0.5 hover:underline"
          )}
        >
          <ArrowLeftIcon className="size-4" />
          Create service
        </Link>

        <h1 className="text-3xl font-bold">New Git Service</h1>
      </div>

      <ul
        className={cn(
          "flex flex-col gap-2 w-full md:w-1/2 relative overflow-auto h-100",
          gitAppList.length === 0 ? "my-20" : "my-6"
        )}
      >
        <h2 className="text-grey">Select a git app</h2>

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
              <GithubAppCardLink app={git_app.github} parent_id={git_app.id} />
            )}
            {git_app.gitlab && (
              <GitlabAppCardLink app={git_app.gitlab} parent_id={git_app.id} />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
