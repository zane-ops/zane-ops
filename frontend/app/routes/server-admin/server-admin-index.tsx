import { href, redirect } from "react-router";
import type { Route } from "./+types/server-admin-index";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(href("/admin/users"));
}
