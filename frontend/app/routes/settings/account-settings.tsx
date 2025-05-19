import { href, redirect } from "react-router";
import type { Route } from "./+types/account-settings";

export function clientLoader() {
  throw redirect(href("/settings/ssh-keys"));
}

export default function UserSettingsPage({}: Route.ComponentProps) {
  return (
    <>
      <h2 className="text-grey italic text-center">✨ Coming soon ✨</h2>
    </>
  );
}
