import type { Route } from "./+types/workspace-details";

export async function clientLoader({ params }: Route.ClientLoaderArgs) {
  // ...
}

export default function WorkspaceDetailsPage({}: Route.ComponentProps) {
  return <>workpace-details Page</>;
}
