import type { Route } from "./+types/swarm-node-services";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function SwarmNodeServicesPage({}: Route.ComponentProps) {
  return <>swarm-node-services Page</>;
}
