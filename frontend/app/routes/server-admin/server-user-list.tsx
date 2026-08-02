import type { Route } from "./+types/server-user-list";

export async function clientLoader({}: Route.ClientLoaderArgs) {
  return;
}

export default function ServerUserListPage({}: Route.ComponentProps) {
  return <>server-user-list Page</>;
}
