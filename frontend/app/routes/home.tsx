import { useQuery } from "@tanstack/react-query";
import { href, redirect } from "react-router";
import { Header } from "~/components/header/header";
import { UserDropdown } from "~/components/header/user-header-dropdown";
import { userQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";

import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/home";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();

  const workspace = await queryClient.ensureQueryData(
    userQueries.currentWorkspace
  );

  if (workspace) {
    throw redirect(
      href("/:workspaceId", {
        workspaceId: workspace.id
      })
    );
  }
}

export default function HomePage({
  matches: {
    "1": { loaderData }
  }
}: Route.ComponentProps) {
  const { data: user } = useQuery({
    ...userQueries.authedUser,
    initialData: loaderData.user
  });

  if (!user) return null;

  return (
    <>
      <Header rigthSlot={<UserDropdown user={user} />} />

      <main
        className={cn(
          "grow container p-6 relative overflow-y-clip",
          "flex flex-col gap-10",
          !import.meta.env.PROD && "my-7"
        )}
      >
        <h1 className="text-2xl font-medium">Dashboard</h1>

        <div
          className={cn(
            "flex flex-col items-center justify-center gap-2 px-6 py-20",
            "border-border rounded-lg w-full border-dashed border-1 text-grey",
            "col-span-full"
          )}
        >
          <h3 className="text-2xl font-medium text-card-foreground">
            Welcome to ZaneOps
          </h3>
          <p>
            Your account isn't part of any workspace yet, so there's nothing to
            show here.
          </p>
          <p>
            Ask your administrator to invite you to a workspace to get started.
          </p>
        </div>
      </main>
    </>
  );
}
