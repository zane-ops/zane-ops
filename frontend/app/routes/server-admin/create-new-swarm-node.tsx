import type { Route } from "./+types/create-new-swarm-node";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function CreateNewSwarmNodePage({}: Route.ComponentProps) {
  return <>create-new-swarm-node Page</>;
}
