import { createLazyFileRoute } from "@tanstack/react-router";
import { withAuthRedirect } from "~/components/helper/auth-redirect";

export const Route = createLazyFileRoute("/dashboard")({
  component: withAuthRedirect(Dashboard)
});

function Dashboard() {
  return <div>hello from dashboard</div>;
}
