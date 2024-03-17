import { Outlet, createRootRoute } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/router-devtools";
import { TailwindIndicator } from "~/components/tailwind-indicator";

export const Route = createRootRoute({
  component: () => (
    <main className="bg-background">
      <Outlet />
      <TailwindIndicator />
      <TanStackRouterDevtools />
    </main>
  )
});
