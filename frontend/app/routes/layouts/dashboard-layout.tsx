import { useQuery } from "@tanstack/react-query";
import { Outlet, href, redirect } from "react-router";
import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import { Header } from "~/components/header/header";
import { ProjectEnvironmentListHeaderHeaderDropdown } from "~/components/header/project-environment-list-header-dropdown";
import { UserHeaderDropdown } from "~/components/header/user-header-dropdown";
import { WorkspaceMembershipListHeaderDropdown } from "~/components/header/workspace-list-header-dropdown";
import { WorkspaceProjectListHeaderDropdown } from "~/components/header/workspace-project-list-header-dropdown";
import { ZaneUpdateNotifier } from "~/components/zane-update-notifier";
import { projectQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, notFound } from "~/lib/utils";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/dashboard-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const [memberships, projects] = await Promise.all([
    queryClient.ensureQueryData(userQueries.memberships),
    queryClient.ensureQueryData(projectQueries.list(params))
  ]);

  if (memberships === null) {
    throw redirect(href("/login"));
  }

  const workspaces = memberships.map((m) => m.workspace.id);
  if (!workspaces.includes(params.workspaceId)) {
    throw notFound("Workspace Not found");
  }

  return {
    projects,
    memberships
  };
}

export default function DashboardLayout({
  loaderData,
  params,
  matches: {
    "1": {
      loaderData: { user }
    }
  }
}: Route.ComponentProps) {
  if (!user || !loaderData.memberships) return null;

  return (
    <>
      <Header
        leftSlot={[
          <WorkspaceMembershipListHeaderDropdown
            memberships={loaderData.memberships}
          />,
          params.projectSlug ? (
            <WorkspaceProjectListHeaderDropdown
              projectList={loaderData.projects}
            />
          ) : null,
          params.envSlug ? <ProjectEnvironmentListHeaderHeaderDropdown /> : null
        ]}
        rigthSlot={[<CommandBarTrigger />, <UserHeaderDropdown user={user} />]}
      />
      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
          !import.meta.env.PROD && "my-7"
        )}
      >
        <Outlet />
        <ZaneUpdateNotifier />
      </main>
    </>
  );
}
