import { href, redirect } from "react-router";
import type { Route } from "./+types/settings-index";

export function clientLoader({ params }: Route.ClientLoaderArgs) {
  throw redirect(
    href("/:workspaceId/settings/account", { workspaceId: params.workspaceId })
  );
}
