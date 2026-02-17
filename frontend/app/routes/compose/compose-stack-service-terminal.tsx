import type { Route } from "./+types/compose-stack-service-terminal";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function ComposeStackServiceTerminalPage({}: Route.ComponentProps) {
  return <>compose-stack-service-terminal Page</>;
}
