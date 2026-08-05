import { href, redirect } from "react-router";
import { getQueryClient } from "~/lib/query-client";
import type { Route } from "./+types/server-user-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/admin/users"));
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  const queryClient = getQueryClient();
}
