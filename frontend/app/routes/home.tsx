import { useQuery } from "@tanstack/react-query";
import { Navigate, href, redirect } from "react-router";
import { Header, UserDropdown } from "~/components/header";
import { userQueries } from "~/lib/queries";
import { cn } from "~/lib/utils";
import { queryClient } from "~/root";
import type { Route } from "./+types/home";

export async function clientLoader({ request }: Route.ClientLoaderArgs) {
  const user = await queryClient.ensureQueryData(userQueries.authedUser);

  if (!user) {
    throw redirect(href("/login"));
  }

  if (user.membership) {
    throw redirect(
      href("/:workspaceId", {
        workspaceId: user.membership.workspace.id
      })
    );
  }
  return { user };
}

export default function HomePage({ loaderData }: Route.ComponentProps) {
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
