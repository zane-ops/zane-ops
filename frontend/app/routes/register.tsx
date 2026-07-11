import type { Route } from "./+types/register";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function RegisterPage({}: Route.ComponentProps) {
  return <>register Page</>;
}
