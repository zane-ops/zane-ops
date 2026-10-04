import type { Route } from "./+types/swarm-node-deployment-logs";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function SwarmNodeDeploymentLogsPage({}: Route.ComponentProps) {
  return <>provision-swarm-node-logs Page</>;
}
