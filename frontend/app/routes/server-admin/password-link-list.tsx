import type { Route } from "./+types/password-link-list";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function PasswordLinkListPage({}: Route.ComponentProps) {
  return <>password-token-list Page</>;
}
