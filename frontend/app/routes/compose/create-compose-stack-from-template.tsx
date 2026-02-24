import type { Route } from "./+types/create-compose-stack-from-template";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function CreateComposeStackFromTemplatePage({}: Route.ComponentProps) {
  return <>create-compose-stack-from-template Page</>;
}
