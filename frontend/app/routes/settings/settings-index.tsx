import { redirect } from "react-router";

export function clientLoader() {
  throw redirect("/settings/account");
}

export default function SettingsIndexPage() {
  return null;
}
