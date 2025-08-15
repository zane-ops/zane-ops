import { Outlet } from "react-router";
import { projectQueries } from "~/lib/queries";
import { isNotFoundError } from "~/lib/utils";
import { queryClient } from "~/root";
import { metaTitle } from "~/utils";
import type { Route } from "./+types/project-layout";

export function meta({ error }: Route.MetaArgs) {
  const title = !error
    ? `Project settings`
    : isNotFoundError(error)
      ? "Error 404 - Project does not exist"
      : "Oops";
  return [metaTitle(title)] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  const project = await queryClient.ensureQueryData(
    projectQueries.single(params.projectSlug)
  );
  return { project };
}

export default function ProjectLayout({}: Route.ComponentProps) {
  return (
    <>
      <Outlet />
    </>
  );
}
