import { Outlet, href, redirect } from "react-router";
import { CommandBarTrigger } from "~/components/commandbar/commandbar-trigger";
import { Header } from "~/components/header/header";
import { ProjectEnvironmentListHeaderHeaderDropdown } from "~/components/header/project-environment-list-header-dropdown";
import { UserHeaderDropdown } from "~/components/header/user-header-dropdown";
import { WorkspaceMembershipListHeaderDropdown } from "~/components/header/workspace-list-header-dropdown";
import { WorkspaceProjectListHeaderDropdown } from "~/components/header/workspace-project-list-header-dropdown";
import { ensureAuthedUser, projectQueries, userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, metaTitle } from "~/lib/utils";
import type { Route } from "./+types/workspace-layout";

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const [memberships, user] = await Promise.all([
    queryClient.ensureQueryData(userQueries.memberships),
    queryClient.ensureQueryData(userQueries.authedUser)
  ]);

  const workspace = user?.membership?.workspace;
  if (memberships === null || !workspace) {
    throw redirect(href("/login"));
  }

  const [projects, currentProject] = await Promise.all([
    queryClient.ensureQueryData(
      projectQueries.list({ workspaceId: workspace.id })
    ),
    params.projectSlug
      ? queryClient.ensureQueryData(
          projectQueries.single(workspace.id, params.projectSlug)
        )
      : undefined
  ]);

  return {
    user,
    workspace,
    projects,
    currentProject,
    memberships
  };
}

export default function WorkspaceLayout({
  loaderData,
  params
}: Route.ComponentProps) {
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
          params.envSlug ? (
            <ProjectEnvironmentListHeaderHeaderDropdown
              currentProject={loaderData.currentProject}
            />
          ) : null
        ]}
        rigthSlot={[
          <CommandBarTrigger />,
          <UserHeaderDropdown user={loaderData.user} />
        ]}
      />
      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
          !import.meta.env.PROD && "my-7"
        )}
      >
        <Outlet />
      </main>
    </>
  );
}
