import type { Route } from "./+types/workpace-details";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function WorkspaceDetailsPage({}: Route.ComponentProps) {
  return <>workpace-details Page</>;
}
