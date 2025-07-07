import type { Route } from "./+types/gitlab-app-details";

export function clientLoader({}: Route.ClientLoaderArgs) {}

export default function GitlabAppDetailsPage({}: Route.ComponentProps) {
  return <>gitlab-app-details Page</>;
}

export async function clientAction({}: Route.ClientActionArgs) {}
