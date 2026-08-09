import type { Route } from "./+types/license-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function LicenseDetailsPage({}: Route.ComponentProps) {
  return <>license-details Page</>;
}
