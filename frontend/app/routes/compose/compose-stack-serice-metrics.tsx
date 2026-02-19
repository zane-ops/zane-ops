import type { Route } from "./+types/compose-stack-serice-metrics";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function ComposeStackServiceMetricsPage({}: Route.ComponentProps) {
  return <>compose-stack-serice-metrics Page</>;
}
