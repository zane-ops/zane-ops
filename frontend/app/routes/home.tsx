import { href, redirect } from "react-router";
import { createDevLogger } from "~/lib/logger";
import { userQueries } from "~/lib/queries";
import { getQueryClient } from "~/lib/query-client";
import { cn, metaTitle } from "~/lib/utils";
import type { Route } from "./+types/home";

const logger = createDevLogger(import.meta.url);

export function meta() {
  return [metaTitle("Dashboard")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  const queryClient = getQueryClient();
  const authedUser = await queryClient.ensureQueryData(userQueries.authedUser);

  const workspace = authedUser?.membership?.workspace;

  if (workspace) {
    logger.info("redirect to `/workspace`");
    throw redirect(href("/workspace"));
  }

  return;
}

export default function HomePage({}: Route.ComponentProps) {
  return (
    <>
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
    </>
  );
}
