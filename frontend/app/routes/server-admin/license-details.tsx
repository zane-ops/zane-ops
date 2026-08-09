import { metaTitle } from "~/lib/utils";
import type { Route } from "./+types/license-details";

export function meta() {
  return [metaTitle("License")] satisfies ReturnType<Route.MetaFunction>;
}

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function LicenseDetailsPage({}: Route.ComponentProps) {
  return <>license-details Page</>;
}
