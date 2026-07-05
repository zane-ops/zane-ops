import { redirect } from "react-router";
import type { Route } from "./+types/switch-workspace";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  throw redirect(`/`);
}

export async function clientAction({ request }: Route.ClientActionArgs) {
  // ...
}
