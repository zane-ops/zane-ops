import * as React from "react";
import { useSearchParams } from "react-router";
import type { Route } from "./+types/terminal-settings";

export default function TerminalSettingsPage({}: Route.ComponentProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [counter, setCounter] = React.useState(0);

  return <>terminal-settings Page</>;
}
